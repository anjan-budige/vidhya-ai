"""
╔══════════════════════════════════════════════════════════════════╗
║  VIDHYA BOT — AI & RAG Orchestrator Service                      ║
║  Provides: Embedding generation, pgvector similarity search,     ║
║  rolling prompt composition, and Ollama SSE chat streaming.      ║
╚══════════════════════════════════════════════════════════════════╝
"""

import json
import time
import uuid
from datetime import datetime, timezone
from typing import AsyncGenerator, Optional, List, Dict, Any, Tuple

import httpx
import redis.asyncio as aioredis
import tiktoken
from fastapi import HTTPException, status
from sqlalchemy import select, Float
from sqlalchemy.orm import joinedload
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.chunk import DocumentChunk
from app.models.document import Document
from app.models.ai_query import AIQuery
from app.models.message import Message
from app.services.conversation import ConversationService
from app.services.quota import QuotaService

settings = get_settings()


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
    async def generate_embedding(text: str) -> List[float]:
        """
        Generate a 1024-dimensional embedding from Mistral API.
        """
        url = "https://api.mistral.ai/v1/embeddings"
        payload = {
            "model": settings.MISTRAL_EMBED_MODEL,
            "input": [text]
        }
        headers = {
            "Authorization": f"Bearer {settings.MISTRAL_API_KEY}",
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(url, json=payload, headers=headers, timeout=15.0)
                response.raise_for_status()
                res_json = response.json()
                
                embedding = res_json.get("data", [{}])[0].get("embedding")
                if not embedding or not isinstance(embedding, list):
                    raise ValueError("Mistral response does not contain a valid embedding vector.")
                    
                return embedding
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Mistral embedding model failed: {str(e)}"
            )

    @staticmethod
    async def retrieve_relevant_chunks(
        query_embedding: List[float],
        limit: int,
        db: AsyncSession
    ) -> List[Tuple[DocumentChunk, float]]:
        """
        Perform a pgvector similarity search on DocumentChunk.
        Strictly limits to processed and active documents.
        """
        # Cosine distance operator <=> in pgvector
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
            
            payload = {
                "model": settings.MISTRAL_CHAT_MODEL,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.3
            }
            headers = {
                "Authorization": f"Bearer {settings.MISTRAL_API_KEY}",
                "Content-Type": "application/json"
            }
            
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    "https://api.mistral.ai/v1/chat/completions",
                    json=payload,
                    headers=headers
                )
                if response.status_code == 200:
                    result = response.json()
                    title = result.get("choices", [{}])[0].get("message", {}).get("content", "").strip()[:50]
                    # Clean up quotes if the model included them
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
            # Yield error event
            yield f"event: error\ndata: {json.dumps({'detail': 'Daily message quota exceeded.'})}\n\n"
            return
            
        # 2. Retrieve Conversation Thread Details
        conv = await ConversationService.get_conversation(conversation_id, db)
        limits = await QuotaService.get_active_subscription_limits(user_id, db, redis)
        
        # 3. Generate query embedding
        try:
            query_embedding = await cls.generate_embedding(query)
        except Exception as e:
            yield f"event: error\ndata: {json.dumps({'detail': f'Embedding generation failed: {str(e)}'})}\n\n"
            return
            
        # 4. Perform Vector Search (if RAG feature is enabled on current subscription plan)
        features = limits.get("features", {})
        rag_enabled = features.get("rag_enabled", True)
        
        chunks: List[Tuple[DocumentChunk, float]] = []
        context_str = ""
        retrieved_refs = []
        
        if rag_enabled:
            chunks = await cls.retrieve_relevant_chunks(query_embedding, limit=5, db=db)
            
            # Formulate context references for prompt context block
            if chunks:
                ref_list = []
                for i, (chunk, dist) in enumerate(chunks):
                    ref_list.append(
                        f"Context chunk:\n{chunk.content}\n"
                    )
                    retrieved_refs.append({
                        "chunk_id": str(chunk.id),
                        "document_name": chunk.document.original_filename,
                        "page": chunk.page_number,
                        "score": float(1 - dist)  # Sim score
                    })
                        
                if ref_list:
                    context_str = "\n".join(ref_list)
                    
        # 5. Extract Rolling Chat Context
        history = await ConversationService.get_rolling_context(conversation_id, db)
        
        # 5.5 Auto-name new conversations using a background task
        if len(history) == 0:
            import asyncio
            asyncio.create_task(cls.generate_conversation_title_task(query, conversation_id))
            
        # 6. Compose LLM Prompt Messages
        system_prompt = (
            "You are Vidhya Bot, a highly intelligent educational AI assistant, developed independently by Vidhya Platform.\n"
            "Under no circumstances should you identify as DeepSeek, OpenAI, Qwen, or any other foundational LLM model.\n"
            "Answer the user's questions as accurately and concisely as possible.\n"
            "CRITICAL: Do NOT output any internal monologue, reasoning, 'let me think' thoughts, or meta-commentary.\n"
            "CRITICAL: Do NOT cite sources, mention document names, or use phrases like 'According to the context'. Seamlessly incorporate the information as your own knowledge.\n"
            "Respond with the final concise answer directly. Never think out loud."
        )
        if rag_enabled:
            if context_str:
                system_prompt += (
                    "\nFirst, try to answer using ONLY the educational context provided below. "
                    "If the context does not contain the answer, you may use your own general knowledge to answer it seamlessly.\n\n"
                    "=== EDUCATIONAL CONTEXT ===\n"
                    f"{context_str}\n"
                    "============================\n"
                )
            else:
                system_prompt += (
                    "\nNo relevant educational documents were found for this query. "
                    "Use your own knowledge to answer the user's question seamlessly without mentioning that documents were not found.\n"
                )
            
        messages = [{"role": "system", "content": system_prompt}]
        
        # Calculate current token usage for prompt to enforce max_context_tokens
        max_context_tokens = limits.get("max_context_tokens", 2000)
        current_context_tokens = count_tokens(system_prompt) + count_tokens(query)
        
        # Inject rolling chat history (enforcing token limits by dropping oldest first)
        history_messages = []
        for msg in reversed(history): # start from newest history
            msg_tokens = msg.token_count if hasattr(msg, "token_count") and msg.token_count else count_tokens(msg.content)
            if current_context_tokens + msg_tokens <= max_context_tokens:
                history_messages.insert(0, {"role": msg.role, "content": msg.content})
                current_context_tokens += msg_tokens
            else:
                break # stop if we exceed max context tokens
                
        messages.extend(history_messages)
            
        # Current User Query
        messages.append({"role": "user", "content": query})
        
        input_tokens = current_context_tokens
        
        # 7. Formulate Mistral chat completion payload
        payload = {
            "model": settings.MISTRAL_CHAT_MODEL,
            "messages": messages,
            "stream": True,
            "temperature": 0.3,
            "max_tokens": limits.get("max_response_tokens", 512),
            "stream_options": {"include_usage": True}
        }
        headers = {
            "Authorization": f"Bearer {settings.MISTRAL_API_KEY}",
            "Content-Type": "application/json"
        }
        
        # 8. Record User Message in Database
        input_tokens = count_tokens(query) + count_tokens(system_prompt)
        user_msg = await ConversationService.add_message(
            conv_id=conversation_id,
            user_id=user_id,
            role="user",
            content=query,
            token_count=input_tokens,
            db=db,
            redis=redis
        )
        
        # Stream response chunks from Ollama
        assistant_content = []
        message_id = uuid.uuid4()
        
        yield f"event: metadata\ndata: {json.dumps({'conversation_id': str(conversation_id), 'user_message_id': str(user_msg.id), 'assistant_message_id': str(message_id)})}\n\n"
        
        try:
            from app.main import logger
            logger.info("mistral.request_payload", payload=payload)
            
            # Variables to hold true usage if Mistral returns it
            mistral_input_tokens = None
            mistral_output_tokens = None
            
            async with httpx.AsyncClient() as client:
                async with client.stream(
                    "POST",
                    "https://api.mistral.ai/v1/chat/completions",
                    json=payload,
                    headers=headers,
                    timeout=float(settings.MISTRAL_REQUEST_TIMEOUT)
                ) as response:
                    
                    response.raise_for_status()
                    
                    async for line in response.aiter_lines():
                        line = line.strip()
                        if not line or line.startswith(":"):
                            continue
                            
                        if line == "data: [DONE]":
                            break
                            
                        if line.startswith("data: "):
                            data_str = line[6:]
                            try:
                                chunk_json = json.loads(data_str)
                                
                                # Extract usage if present (requires stream_options: {"include_usage": true})
                                usage = chunk_json.get("usage")
                                if usage:
                                    mistral_input_tokens = usage.get("prompt_tokens")
                                    mistral_output_tokens = usage.get("completion_tokens")
                                    
                                choices = chunk_json.get("choices", [])
                                if choices:
                                    delta = choices[0].get("delta", {})
                                    token = delta.get("content", "")
                                    
                                    if token:
                                        assistant_content.append(token)
                                        yield f"event: token\ndata: {json.dumps({'token': token})}\n\n"
                                        
                            except json.JSONDecodeError:
                                logger.warning(f"Failed to parse Mistral SSE chunk: {data_str}")
                                continue
                                
        except Exception as e:
            yield f"event: error\ndata: {json.dumps({'detail': f'Mistral generation error: {str(e)}'})}\n\n"
            return
            
        # 9. Register Assistant Response in Database
        response_text = "".join(assistant_content)
        
        # Use exact Mistral tokens if available, fallback to tiktoken approximation
        final_input_tokens = mistral_input_tokens if mistral_input_tokens is not None else input_tokens
        final_output_tokens = mistral_output_tokens if mistral_output_tokens is not None else count_tokens(response_text)
        
        # Calculate RAG metadata
        confidence_val = None
        if retrieved_refs:
            # Average score of references as confidence score
            confidence_val = sum(r["score"] for r in retrieved_refs) / len(retrieved_refs)
            
        # Write response message to DB
        assistant_msg = Message(
            id=message_id,
            conversation_id=conversation_id,
            user_id=user_id,
            role="assistant",
            content=response_text,
            token_count=final_output_tokens,
            retrieved_chunks={"references": retrieved_refs} if retrieved_refs else None,
            confidence_score=confidence_val,
            was_cached=False,
            is_in_context=True,
            is_summarized=False,
            created_at=datetime.now(timezone.utc)
        )
        db.add(assistant_msg)
        
        # Update conversation aggregates
        conv.total_messages = conv.total_messages + 1
        conv.total_tokens_used = conv.total_tokens_used + final_output_tokens
        conv.last_activity_at = datetime.now(timezone.utc)
        
        # Trigger Quota Increments
        await QuotaService.increment_quota(user_id, "messages", 1, db, redis, tokens_input=final_input_tokens, tokens_output=final_output_tokens)
        
        # 10. Audit log into ai_queries table
        latency_ms = int((time.time() - start_time) * 1000)
        
        ai_query_log = AIQuery(
            user_id=user_id,
            conversation_id=conversation_id,
            message_id=assistant_msg.id,
            query_text=query,
            response_text=response_text,
            chunks_retrieved=len(retrieved_refs),
            retrieval_score=confidence_val,
            tokens_input=final_input_tokens,
            tokens_output=final_output_tokens,
            total_tokens=final_input_tokens + final_output_tokens,
            response_time_ms=latency_ms,
            model_used=settings.MISTRAL_CHAT_MODEL,
            was_cached=False,
            created_at=datetime.now(timezone.utc)
        )
        db.add(ai_query_log)
        await db.flush()
        await db.commit()  # CRITICAL: commit all writes (messages, conversation, ai_queries) before stream closes
        
        # Final Event
        yield f"event: done\ndata: {json.dumps({'status': 'completed'})}\n\n"
    

