import json
import logging
import time
import uuid
from datetime import datetime, timezone
from typing import AsyncGenerator, Optional, List, Dict, Any, Tuple

import httpx
import redis.asyncio as aioredis
import tiktoken
from fastapi import HTTPException, status
from sqlalchemy import select, Float, func
from sqlalchemy.orm import joinedload
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.chunk import DocumentChunk
from app.models.document import Document
from app.models.ai_query import AIQuery
from app.models.message import Message
from app.services.ai_providers import AIConfig, AIConfigError, AIProviderService
from app.services.conversation import ConversationService
from app.services.prompts import DEFAULT_SYSTEM_PROMPT, FORMATTING_RULES
from app.services.quota import QuotaService

settings = get_settings()
logger = logging.getLogger("vidhya.ai")


def _cosine(a: List[float], b: List[float]) -> float:
    """Cosine similarity for two same-length vectors; 0.0 when incomparable."""
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = sum(x * x for x in a) ** 0.5
    norm_b = sum(y * y for y in b) ** 0.5
    if not norm_a or not norm_b:
        return 0.0
    return dot / (norm_a * norm_b)


def count_tokens(text: str) -> int:
    """Count tokens in a text block using tiktoken."""
    try:
        # Using cl100k_base which is standard for newer OpenAI models / similar tokenizers
        encoding = tiktoken.get_encoding("cl100k_base")
        return len(encoding.encode(text))
    except Exception:
        # Fallback: approximate 1 token = 4 characters
        return max(1, len(text) // 4)


class AIService:
    """Orchestrates Ollama interactions, pgvector similarity search, and streaming responses."""

    @staticmethod
    async def generate_embedding(text: str, config: AIConfig) -> List[float]:
        """Generate an embedding with the configured embedding model."""
        try:
            return await AIProviderService.embed(config, text)
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Embedding model failed: {str(e)}",
            )

    @staticmethod
    async def retrieve_relevant_chunks(
        query_embedding: List[float],
        limit: int,
        db: AsyncSession,
        model_id: Optional[str] = None,
        min_score: float = 0.0,
    ) -> List[Tuple[DocumentChunk, float]]:
        """
        Perform a pgvector similarity search on DocumentChunk.
        Only chunks embedded by the active embedding model are eligible, so
        vectors from different models are never compared. Chunks scoring below
        min_score are dropped in SQL, so weak matches never reach the prompt
        or the citation badges.
        """
        # Cosine distance operator <=> in pgvector; similarity = 1 - distance
        distance = DocumentChunk.embedding.op("<=>", return_type=Float())(query_embedding).label("distance")
        
        stmt = (
            select(DocumentChunk, distance)
            .join(Document, Document.id == DocumentChunk.document_id)
            .where(Document.is_active == True)
            .where(Document.status == "processed")
            .options(joinedload(DocumentChunk.document))
            .order_by(distance.asc())
            .limit(limit)
        )

        if min_score > 0:
            stmt = stmt.where(distance <= 1 - min_score)

        if model_id:
            stmt = stmt.where(
                DocumentChunk.embedding_model_id == uuid.UUID(model_id)
            )

        result = await db.execute(stmt)
        # Returns list of tuple (DocumentChunk, distance)
        return list(result.all())

    @staticmethod
    async def generate_conversation_title_task(query: str, conv_id: uuid.UUID) -> None:
        """
        Background task to auto-generate a concise 3-word title for a new conversation based on the first query.
        """
        try:
            from app.database import async_session_factory
            from app.models.conversation import Conversation
            from sqlalchemy import update
            
            prompt = (
                f"Generate a concise, maximum 3-word title summarizing this user query: '{query}'. "
                "Do not include quotes, periods, or extra text. Just the title."
            )
            
            chat_cfg = AIProviderService.get_default_sync("chat")
            title = AIProviderService.complete_sync(
                chat_cfg,
                [{"role": "user", "content": prompt}],
                max_tokens=24,
                temperature=0.3,
            ).strip()[:50]
            title = title.replace('"', '').replace("'", "")

            if title:
                async with async_session_factory() as session:
                    await session.execute(
                        update(Conversation)
                        .where(Conversation.id == conv_id)
                        .values(title=title, last_activity_at=datetime.now(timezone.utc))
                    )
                    await session.commit()
        except Exception as e:
            from app.main import logger
            import traceback
            logger.error(f"Failed to auto-generate conversation title: {e}\n{traceback.format_exc()}")

    @staticmethod
    async def _summarize_messages(
        config: AIConfig,
        messages: List[Message],
        target_tokens: int,
        previous_summary: str = "",
    ) -> str:
        """Compress a block of history into a short, fact-preserving summary."""
        transcript = "\n".join(
            f"{m.role.capitalize()}: {m.content}" for m in messages
        )
        if previous_summary:
            transcript = (
                f"Existing summary:\n{previous_summary}\n\n"
                f"New messages to merge:\n{transcript}"
            )

        prompt = (
            "You compress conversation history for an AI tutor. Preserve facts, "
            "names, definitions, the user's goals and decisions. Remove small talk. "
            f"Return only a concise summary of at most {target_tokens} tokens.\n\n"
            f"{transcript}"
        )

        try:
            summary = await AIProviderService.complete(
                config,
                [
                    {
                        "role": "system",
                        "content": "You summarize conversations faithfully and concisely.",
                    },
                    {"role": "user", "content": prompt},
                ],
                max_tokens=target_tokens,
                temperature=0.2,
            )
            return summary.strip() or transcript[: target_tokens * 4]
        except Exception as e:
            logger.warning("context.compression_failed: %s", e)
            return transcript[: target_tokens * 4]

    @classmethod
    async def _build_context(
        cls,
        conv,
        system_prompt: str,
        query: str,
        db: AsyncSession,
        chat_config: AIConfig,
        max_tokens: int,
    ):
        """
        Return (summary, messages) for the prompt.
        Sends all history when it fits; otherwise summarizes the older part
        into 20% of the context window and keeps the newest messages.
        """
        history = await ConversationService.get_context_messages(conv.id, db)
        summary = conv.summary_text or ""

        def msg_tokens(m: Message) -> int:
            return m.token_count or count_tokens(m.content)

        total = (
            count_tokens(system_prompt)
            + count_tokens(query)
            + count_tokens(summary)
            + sum(msg_tokens(m) for m in history)
        )
        if total <= max_tokens:
            return summary, history

        available = max_tokens - count_tokens(system_prompt) - count_tokens(query)
        summary_budget = max(
            100,
            min(int(max_tokens * 0.20), max(0, int(available * 0.30))),
        )
        remaining = max(0, available - summary_budget)

        keep: List[Message] = []
        used = 0
        for msg in reversed(history):
            tokens = msg_tokens(msg)
            if used + tokens > remaining:
                break
            keep.insert(0, msg)
            used += tokens

        keep_ids = {m.id for m in keep}
        older = [m for m in history if m.id not in keep_ids]

        if older:
            merged = await cls._summarize_messages(
                chat_config, older, summary_budget, summary
            )
            if count_tokens(merged) > summary_budget:
                merged = merged[: summary_budget * 4]
            conv.summary_text = merged
            for msg in older:
                msg.is_summarized = True
                msg.is_in_context = False
            await db.flush()
            summary = merged

        return summary, keep

    @classmethod
    async def generate_response_stream(
        cls,
        user_id: uuid.UUID,
        conversation_id: uuid.UUID,
        query: str,
        db: AsyncSession,
        redis: aioredis.Redis
    ) -> AsyncGenerator[str, None]:
        """
        Check quota, compile chat prompt with rolling history and RAG chunks,
        stream tokens via Server-Sent Events (SSE) and audit performance.
        """
        start_time = time.time()
        
        # 0. Prompt Injection Keyword Block-List check
        blocked_keywords = [
            "ignore previous instructions", "system prompt", "bypass",
            "developer mode", "jailbreak", "do anything now", "dan",
            "forget all instructions", "you are no longer", "sudo",
            "you are now", "what are your instructions"
        ]
        lower_query = query.lower()
        if any(keyword in lower_query for keyword in blocked_keywords):
            yield f"event: error\ndata: {json.dumps({'detail': 'Request blocked due to security policy violation.'})}\n\n"
            return
        
        # 1. Quota Check
        allowed, details = await QuotaService.check_quota(user_id, "messages", 1, db, redis)
        if not allowed:
            yield f"event: error\ndata: {json.dumps({'detail': 'Daily message quota exceeded.'})}\n\n"
            return
            
        # 2. Retrieve Conversation Thread Details
        conv = await ConversationService.get_conversation(conversation_id, db)
        limits = await QuotaService.get_active_subscription_limits(user_id, db, redis)

        try:
            chat_config = await AIProviderService.get_default(db, redis, "chat")
        except AIConfigError as e:
            logger.error("ai.chat_model_unavailable: %s", e)
            yield (
                "event: error\ndata: "
                + json.dumps(
                    {
                        "detail": (
                            "The AI assistant is not available right now. "
                            "Please try again in a few minutes."
                        )
                    }
                )
                + "\n\n"
            )
            return

        max_response_tokens = max(
            64,
            min(limits.get("max_response_tokens", 512), chat_config.max_output_tokens),
        )
        plan_context_tokens = int(limits.get("max_context_tokens", 2000))
        effective_context_tokens = max(
            256,
            min(
                plan_context_tokens,
                chat_config.context_window - max_response_tokens - 128,
            ),
        )

        # 3/4. RAG (only when enabled on the plan)
        features = limits.get("features", {})
        rag_enabled = features.get("rag_enabled", True)

        chunks: List[Tuple[DocumentChunk, float]] = []
        context_str = ""
        retrieved_refs: List[Dict[str, Any]] = []
        cited_chunks: List[Tuple[Dict[str, Any], DocumentChunk]] = []
        embedding_config = None

        if rag_enabled:
            try:
                embedding_config = await AIProviderService.get_default(
                    db, redis, "embedding"
                )
                query_embedding = await AIProviderService.embed(embedding_config, query)
                chunks = await cls.retrieve_relevant_chunks(
                    query_embedding,
                    limit=settings.RAG_TOP_K,
                    db=db,
                    model_id=embedding_config.model_id,
                    min_score=settings.RAG_MIN_SCORE,
                )
            except Exception as e:
                # No embedding provider yet: answer without documents instead of failing.
                logger.warning("RAG unavailable, answering without documents: %s", e)
                rag_enabled = False
                chunks = []
            
            if chunks:
                ref_list = []
                cited_pages = set()
                rag_budget = max(200, int(effective_context_tokens * 0.35))
                rag_used = 0
                for i, (chunk, dist) in enumerate(chunks):
                    text = (chunk.content or "").strip()
                    if not text:
                        continue
                    chunk_tokens = count_tokens(text)
                    if rag_used + chunk_tokens > rag_budget:
                        remaining_chars = max(0, (rag_budget - rag_used) * 4)
                        if remaining_chars >= 100:
                            ref_list.append(f"Context chunk:\n{text[:remaining_chars]}\n")
                        break
                    ref_list.append(f"Context chunk:\n{text}\n")
                    rag_used += chunk_tokens
                    page_key = (chunk.document_id, chunk.page_number)
                    if page_key not in cited_pages:
                        cited_pages.add(page_key)
                        ref = {
                            "chunk_id": str(chunk.id),
                            "document_name": chunk.document.original_filename,
                            "page": chunk.page_number,
                            "score": float(1 - dist)  # Sim score
                        }
                        retrieved_refs.append(ref)
                        cited_chunks.append((ref, chunk))
                        
                if ref_list:
                    context_str = "\n".join(ref_list)
                    
        # 5. Auto-name a brand-new session
        if conv.total_messages == 0:
            import asyncio
            asyncio.create_task(cls.generate_conversation_title_task(query, conversation_id))
            
        # 6. Compose LLM Prompt Messages
        system_prompt = (
            chat_config.system_prompt.strip()
            if chat_config.system_prompt
            else DEFAULT_SYSTEM_PROMPT
        )
        if rag_enabled:
            if context_str:
                system_prompt += (
                    "\nUse the educational context below when it actually answers the "
                    "question. If the context is unrelated, ignore it completely and "
                    "answer from your own knowledge instead of forcing it in.\n\n"
                    "=== EDUCATIONAL CONTEXT ===\n"
                    f"{context_str}\n"
                    "============================\n"
                )
            else:
                system_prompt += (
                    "\nNo relevant educational documents were found for this query. "
                    "Use your own knowledge to answer the user's question seamlessly without mentioning that documents were not found.\n"
                )
            
        summary, history = await cls._build_context(
            conv,
            system_prompt,
            query,
            db,
            chat_config,
            effective_context_tokens,
        )
        if summary:
            system_prompt += (
                "\n\n=== EARLIER CONVERSATION SUMMARY ===\n"
                f"{summary}\n"
                "=====================================\n"
            )

        system_prompt += FORMATTING_RULES

        messages = [{"role": "system", "content": system_prompt}]
        messages.extend(
            {"role": m.role, "content": m.content} for m in history
        )
            
        messages.append({"role": "user", "content": query})
        
        # 7. Record User Message in Database
        input_tokens = sum(count_tokens(m["content"]) for m in messages)
        user_msg = await ConversationService.add_message(
            conv_id=conversation_id,
            user_id=user_id,
            role="user",
            content=query,
            token_count=count_tokens(query),
            db=db,
            redis=redis
        )
        user_message_id = user_msg.id
        # The request session is rolled back when a client disconnects mid
        # stream, so the question is committed before the answer starts.
        await db.commit()

        assistant_content: List[str] = []
        message_id = uuid.uuid4()
        provider_input_tokens: Optional[int] = None
        provider_output_tokens: Optional[int] = None
        generation_failed = False

        yield f"event: metadata\ndata: {json.dumps({'conversation_id': str(conversation_id), 'user_message_id': str(user_message_id), 'assistant_message_id': str(message_id)})}\n\n"

        try:
            async for event in AIProviderService.stream_chat(
                chat_config,
                messages,
                max_tokens=max_response_tokens,
                temperature=0.3,
            ):
                if event["type"] == "token":
                    assistant_content.append(event["text"])
                    yield f"event: token\ndata: {json.dumps({'token': event['text']})}\n\n"
                elif event["type"] == "usage":
                    provider_input_tokens = event.get("input")
                    provider_output_tokens = event.get("output")
                elif event["type"] == "done":
                    break

        except Exception as e:
            logger.exception("ai.generation_failed")
            generation_failed = True
        finally:
            # Runs on normal completion, provider failure and client disconnect,
            # so a stopped answer is still saved and counted.
            response_text = "".join(assistant_content)
            if response_text:
                if (settings.RAG_CITATION_MODE or "grounded").lower() == "inserted":
                    retrieved_refs = [ref for ref, _ in cited_chunks]
                else:
                    retrieved_refs = await cls.ground_refs(
                        response_text, cited_chunks, embedding_config
                    )
                # Use provider-reported tokens if available, fallback to tiktoken
                final_input_tokens = (
                    provider_input_tokens
                    if provider_input_tokens is not None
                    else input_tokens
                )
                final_output_tokens = (
                    provider_output_tokens
                    if provider_output_tokens is not None
                    else count_tokens(response_text)
                )
                confidence_val = (
                    sum(r["score"] for r in retrieved_refs) / len(retrieved_refs)
                    if retrieved_refs
                    else None
                )
                await cls._finalize_exchange(
                    user_id=user_id,
                    conversation_id=conversation_id,
                    query=query,
                    response_text=response_text,
                    assistant_message_id=message_id,
                    retrieved_refs=retrieved_refs,
                    confidence_val=confidence_val,
                    final_input_tokens=final_input_tokens,
                    final_output_tokens=final_output_tokens,
                    model_used=chat_config.model,
                    latency_start=start_time,
                )

        if generation_failed:
            yield (
                "event: error\ndata: "
                + json.dumps(
                    {
                        "detail": (
                            "The assistant could not complete that answer. "
                            "Please try again."
                        )
                    }
                )
                + "\n\n"
            )
            return

        if retrieved_refs:
            yield (
                "event: sources\ndata: "
                + json.dumps({"sources": retrieved_refs})
                + "\n\n"
            )

        yield f"event: done\ndata: {json.dumps({'status': 'completed'})}\n\n"

    @classmethod
    async def ground_refs(
        cls,
        answer: str,
        cited: List[Tuple[Dict[str, Any], DocumentChunk]],
        embedding_config: Optional[AIConfig],
    ) -> List[Dict[str, Any]]:
        """
        Keep only the chunks the answer is actually grounded in. Retrieval
        matches the question; this check compares the finished answer against
        each chunk, so a badge only appears when the reply used that passage.
        """
        if not cited:
            return []
        if embedding_config is None:
            return [ref for ref, _ in cited if ref["score"] >= settings.RAG_ANSWER_FALLBACK_SCORE]
        try:
            answer_vec = await AIProviderService.embed(embedding_config, answer[:4000])
        except Exception as e:
            logger.warning("Answer grounding check unavailable: %s", e)
            return [ref for ref, _ in cited if ref["score"] >= settings.RAG_ANSWER_FALLBACK_SCORE]

        grounded = []
        for ref, chunk in cited:
            vector = chunk.embedding
            if vector is None:
                continue
            similarity = _cosine(answer_vec, [float(v) for v in vector])
            if similarity >= settings.RAG_ANSWER_MIN_SCORE:
                ref["grounding"] = round(similarity, 4)
                grounded.append(ref)
        return grounded

    @classmethod
    async def _finalize_exchange(
        cls,
        *,
        user_id: uuid.UUID,
        conversation_id: uuid.UUID,
        query: str,
        response_text: str,
        assistant_message_id: uuid.UUID,
        retrieved_refs: List[Dict[str, Any]],
        confidence_val: Optional[float],
        final_input_tokens: int,
        final_output_tokens: int,
        model_used: str,
        latency_start: float,
    ) -> None:
        """
        Write the assistant message, conversation counters, quota and audit row.
        Uses its own session because the request session is already gone when
        the stream ends from a client disconnect.
        """
        from app.database import async_session_factory
        from app.models.conversation import Conversation
        from app.redis_client import redis_client

        now = datetime.now(timezone.utc)
        async with async_session_factory() as session:
            session.add(
                Message(
                    id=assistant_message_id,
                    conversation_id=conversation_id,
                    user_id=user_id,
                    role="assistant",
                    content=response_text,
                    token_count=final_output_tokens,
                    retrieved_chunks=(
                        {"references": retrieved_refs} if retrieved_refs else None
                    ),
                    confidence_score=confidence_val,
                    was_cached=False,
                    is_in_context=True,
                    is_summarized=False,
                    created_at=now,
                )
            )

            conv = (
                await session.execute(
                    select(Conversation).where(Conversation.id == conversation_id)
                )
            ).scalar_one_or_none()
            if conv:
                conv.total_messages = conv.total_messages + 1
                conv.total_tokens_used = conv.total_tokens_used + final_output_tokens
                conv.last_activity_at = now

            await QuotaService.increment_quota(
                user_id,
                "messages",
                1,
                session,
                redis_client,
                tokens_input=final_input_tokens,
                tokens_output=final_output_tokens,
            )

            session.add(
                AIQuery(
                    user_id=user_id,
                    conversation_id=conversation_id,
                    message_id=assistant_message_id,
                    query_text=query,
                    response_text=response_text,
                    chunks_retrieved=len(retrieved_refs),
                    retrieval_score=confidence_val,
                    tokens_input=final_input_tokens,
                    tokens_output=final_output_tokens,
                    total_tokens=final_input_tokens + final_output_tokens,
                    response_time_ms=int((time.time() - latency_start) * 1000),
                    model_used=model_used,
                    was_cached=False,
                    created_at=now,
                )
            )
            await session.commit()
    

