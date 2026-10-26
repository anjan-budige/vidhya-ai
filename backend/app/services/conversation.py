import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Tuple

import redis.asyncio as aioredis
from fastapi import HTTPException, status
from sqlalchemy import select, update, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.conversation import Conversation
from app.models.message import Message
from app.models.subscription import UserSubscription
from app.services.quota import QuotaService

settings = get_settings()


class ConversationService:
    """Manages saved chat sessions and their rolling context windows."""

    @classmethod
    async def create_conversation(
        cls,
        user_id: uuid.UUID,
        title: Optional[str],
        db: AsyncSession,
        redis: aioredis.Redis
    ) -> Conversation:
        """
        Provision a new saved chat session.
        The only limit is max_sessions; sessions are never closed automatically.
        """
        limits = await QuotaService.get_active_subscription_limits(user_id, db, redis)
        max_sessions = limits.get("max_sessions", 5)

        session_count = (
            await db.execute(
                select(func.count(Conversation.id)).where(
                    Conversation.user_id == user_id
                )
            )
        ).scalar() or 0

        if max_sessions != -1 and session_count >= max_sessions:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    f"Session limit reached ({session_count}/{max_sessions}). "
                    "Delete an existing chat to start a new one."
                ),
            )

        sub_result = await db.execute(
            select(UserSubscription)
            .where(UserSubscription.user_id == user_id)
            .where(UserSubscription.status == "active")
        )
        subscription = sub_result.scalar_one_or_none()

        conversation = Conversation(
            user_id=user_id,
            subscription_id=subscription.id if subscription else None,
            title=title or f"Chat session {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            max_context_tokens=limits.get("max_context_tokens", 2000),
            memory_retention_days=limits.get("memory_retention_days", 7),
            total_messages=0,
            total_tokens_used=0,
            messages_since_summary=0,
            started_at=datetime.now(timezone.utc),
            last_activity_at=datetime.now(timezone.utc),
            created_at=datetime.now(timezone.utc)
        )
        
        db.add(conversation)
        
        # If user subscription is active, increment lifetime thread counter
        if subscription:
            subscription.total_conversations = subscription.total_conversations + 1
            
        await db.flush()
        return conversation

    @staticmethod
    async def get_conversation(
        conv_id: uuid.UUID,
        db: AsyncSession
    ) -> Conversation:
        """Retrieve conversation by ID, or raise 404."""
        result = await db.execute(
            select(Conversation).where(Conversation.id == conv_id)
        )
        conversation = result.scalar_one_or_none()
        if not conversation:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Conversation thread not found."
            )
        return conversation

    @classmethod
    async def add_message(
        cls,
        conv_id: uuid.UUID,
        user_id: uuid.UUID,
        role: str,  # 'user' | 'assistant' | 'system'
        content: str,
        token_count: int,
        db: AsyncSession,
        redis: aioredis.Redis,
        retrieved_chunks: Optional[dict] = None,
        confidence_score: Optional[float] = None,
        was_cached: bool = False
    ) -> Message:
        """
        Record a chat message within the conversation.
        Updates last activity timestamps and triggers summaries if necessary.
        """
        conv = await cls.get_conversation(conv_id, db)

        now = datetime.now(timezone.utc)

        # 1. Create message
        message = Message(
            conversation_id=conv_id,
            user_id=user_id,
            role=role,
            content=content,
            token_count=token_count,
            retrieved_chunks=retrieved_chunks,
            confidence_score=confidence_score,
            was_cached=was_cached,
            is_in_context=True,
            is_summarized=False,
            created_at=now
        )
        db.add(message)
        
        # 2. Update Conversation Counters
        conv.total_messages = conv.total_messages + 1
        conv.total_tokens_used = conv.total_tokens_used + token_count
        conv.messages_since_summary = conv.messages_since_summary + 1
        conv.last_activity_at = now
        
        sub_result = await db.execute(
            select(UserSubscription)
            .where(UserSubscription.user_id == user_id)
            .where(UserSubscription.status == "active")
        )
        subscription = sub_result.scalar_one_or_none()
        if subscription:
            subscription.total_messages_used = subscription.total_messages_used + 1
            subscription.total_tokens_consumed = subscription.total_tokens_consumed + token_count
            
        # 3. Check for Summarization trigger (Celery task integration)
        limits = await QuotaService.get_active_subscription_limits(user_id, db, redis)
        summary_freq = limits.get("summary_frequency", 10)
        
        if conv.messages_since_summary >= summary_freq:
            try:
                from app.workers.conversation_summarizer import summarize_conversation
                summarize_conversation.apply_async(
                    args=[str(conv_id)],
                    queue="conversations"
                )
            except Exception:
                pass  # Celery broker offline — summarization will run on next worker sweep
                
        await db.flush()
        return message

    @classmethod
    async def get_context_messages(
        cls,
        conv_id: uuid.UUID,
        db: AsyncSession
    ) -> List[Message]:
        """Return every unsummarized in-context message, oldest first."""
        result = await db.execute(
            select(Message)
            .where(Message.conversation_id == conv_id)
            .where(Message.is_in_context == True)
            .where(Message.is_summarized == False)
            .order_by(Message.created_at.asc())
        )
        return list(result.scalars().all())
