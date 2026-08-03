"""
╔══════════════════════════════════════════════════════════════════╗
║  VIDHYA BOT — Conversation & Thread Service                      ║
║  Provides: Thread provisioning, lazy timeout checks, context     ║
║  window management, and message auditing.                        ║
╚══════════════════════════════════════════════════════════════════╝
"""

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
    """Manages chat session lifecycle, rolling contexts, and inactive timeouts."""

    @classmethod
    async def run_lazy_timeout_check(
        cls,
        user_id: uuid.UUID,
        db: AsyncSession
    ) -> None:
        """
        Check all active conversations of a user and lazily close those
        that have exceeded their inactivity timeout.
        """
        now = datetime.now(timezone.utc)
        
        # Select active conversations
        result = await db.execute(
            select(Conversation)
            .where(Conversation.user_id == user_id)
            .where(Conversation.status == "active")
        )
        active_conversations = result.scalars().all()
        
        for conv in active_conversations:
            timeout_limit = timedelta(minutes=conv.conversation_timeout_min)
            if now - conv.last_activity_at > timeout_limit:
                conv.status = "timeout"
                conv.closed_at = now
                conv.auto_close_reason = "Idle inactivity timeout."
                
        await db.flush()

    @classmethod
    async def create_conversation(
        cls,
        user_id: uuid.UUID,
        title: Optional[str],
        db: AsyncSession,
        redis: aioredis.Redis
    ) -> Conversation:
        """
        Provision a new conversation.
        Enforces concurrent thread limits by running a lazy timeout check first.
        """
        # 1. Run lazy timeout checks first
        await cls.run_lazy_timeout_check(user_id, db)
        
        # 2. Get active limits
        limits = await QuotaService.get_active_subscription_limits(user_id, db, redis)
        max_active_threads = limits.get("max_active_conversations", 1)
        
        # 3. Check concurrent active conversation count
        result = await db.execute(
            select(func.count(Conversation.id))
            .where(Conversation.user_id == user_id)
            .where(Conversation.status == "active")
        )
        active_count = result.scalar() or 0
        
        if active_count >= max_active_threads:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Active conversation limit reached ({active_count}/{max_active_threads}). "
                    "Please close an existing thread before starting a new one."
                )
            )
            
        # Get active subscription ID to link and check total lifetime limits
        sub_result = await db.execute(
            select(UserSubscription)
            .where(UserSubscription.user_id == user_id)
            .where(UserSubscription.status == "active")
        )
        subscription = sub_result.scalar_one_or_none()
        
        if subscription:
            max_conversations = limits.get("max_conversations", 3)
            # -1 usually denotes unlimited, so we check if it's not -1
            if max_conversations != -1:
                # Count current existing conversations instead of lifetime
                existing_count_result = await db.execute(
                    select(func.count(Conversation.id)).where(Conversation.user_id == user_id)
                )
                existing_count = existing_count_result.scalar() or 0
                
                if existing_count >= max_conversations:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail=f"You have reached the maximum allowed saved conversations ({max_conversations}) for your plan. Please delete older chats to start a new one."
                    )
                
        # 4. Create new Conversation
        conversation = Conversation(
            user_id=user_id,
            subscription_id=subscription.id if subscription else None,
            title=title or f"Chat session {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            status="active",
            max_context_messages=limits.get("max_context_messages", 5),
            max_context_tokens=limits.get("max_context_tokens", 2000),
            conversation_timeout_min=limits.get("conversation_timeout_min", 30),
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
    async def close_conversation(
        cls,
        conv_id: uuid.UUID,
        reason: str,
        db: AsyncSession
    ) -> Conversation:
        """Mark a conversation status as closed."""
        conv = await cls.get_conversation(conv_id, db)
        if conv.status == "active":
            conv.status = "closed"
            conv.closed_at = datetime.now(timezone.utc)
            conv.auto_close_reason = reason
            await db.flush()
        return conv

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
        
        # Enforce writing only to active sessions
        # (If timed out, we lazily mark it timed out. Let's run a check)
        now = datetime.now(timezone.utc)
        if conv.status == "active":
            timeout_limit = timedelta(minutes=conv.conversation_timeout_min)
            if now - conv.last_activity_at > timeout_limit:
                conv.status = "timeout"
                conv.closed_at = now
                conv.auto_close_reason = "Idle inactivity timeout."
                await db.flush()
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Cannot post to timed out conversation. Please start a new session."
                )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Conversation thread is closed."
            )
            
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
        
        # Increment active subscription aggregate token counters
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
            # Trigger background summarizer task via Celery
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
    async def get_rolling_context(
        cls,
        conv_id: uuid.UUID,
        db: AsyncSession
    ) -> List[Message]:
        """
        Retrieve list of unsummarized messages inside the active rolling context window.
        """
        conv = await cls.get_conversation(conv_id, db)
        
        # Query messages in the conversation that are in context and not summarized
        result = await db.execute(
            select(Message)
            .where(Message.conversation_id == conv_id)
            .where(Message.is_in_context == True)
            .where(Message.is_summarized == False)
            .order_by(Message.created_at.asc())
        )
        messages = result.scalars().all()
        
        # Return truncated list within max_context_messages limits
        return list(messages)[-conv.max_context_messages:]
