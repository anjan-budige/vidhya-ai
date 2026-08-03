"""
╔══════════════════════════════════════════════════════════════════╗
║  VIDHYA BOT — AI Router                                          ║
║  Provides: SSE chat completion stream events, active quota checks ║
║  and audit query historical lists.                               ║
╚══════════════════════════════════════════════════════════════════╝
"""

import json
from typing import List

import redis.asyncio as aioredis
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import (
    get_db,
    get_redis_client,
    get_current_user,
    get_pagination
)
from app.models.conversation import Conversation
from app.models.ai_query import AIQuery
from app.services.ai import AIService
from app.services.conversation import ConversationService
from app.services.quota import QuotaService
from app.schemas.ai import (
    AIChatRequest,
    AIQuotaResponse,
    AIHistoryItem
)
from app.schemas.auth import CurrentUser
from app.schemas.base import PaginationParams

router = APIRouter(prefix="/ai", tags=["AI Orchestration"])


@router.post("/chat/stream", status_code=status.HTTP_200_OK)
async def ai_chat_stream(
    payload: AIChatRequest,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    redis: aioredis.Redis = Depends(get_redis_client)
):
    """
    Submit user query to AI.
    Returns real-time token stream via Server-Sent Events (SSE).
    """
    # 1. Resolve target conversation thread ID
    conversation_id = payload.conversation_id
    if not conversation_id:
        # Fast path check for active threads
        await ConversationService.run_lazy_timeout_check(current_user.id, db)
        await db.commit()
        
        result = await db.execute(
            select(Conversation)
            .where(Conversation.user_id == current_user.id)
            .where(Conversation.status == "active")
        )
        active_conv = result.scalar_one_or_none()
        
        if active_conv:
            conversation_id = active_conv.id
        else:
            # Auto-provision a new thread
            new_conv = await ConversationService.create_conversation(
                user_id=current_user.id,
                title=f"Chat {payload.message[:20]}...",
                db=db,
                redis=redis
            )
            await db.commit()
            conversation_id = new_conv.id
            
    # Validate provided conversation_id to ensure it's still active
    if payload.conversation_id:
        from app.services.conversation import ConversationService
        from datetime import datetime, timezone, timedelta
        
        conv = await ConversationService.get_conversation(conversation_id, db)
        now = datetime.now(timezone.utc)
        
        if conv.status == "active":
            timeout_limit = timedelta(minutes=conv.conversation_timeout_min)
            if now - conv.last_activity_at > timeout_limit:
                 conv.status = "timeout"
                 conv.closed_at = now
                 conv.auto_close_reason = "Idle inactivity timeout."
                 await db.commit()
                 raise HTTPException(
                     status_code=status.HTTP_400_BAD_REQUEST,
                     detail="Conversation timed out. Please start a new session."
                 )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Conversation thread is closed."
            )
            
    # 2. Return SSE response stream
    generator = AIService.generate_response_stream(
        user_id=current_user.id,
        conversation_id=conversation_id,
        query=payload.message,
        db=db,
        redis=redis
    )
    
    return StreamingResponse(
        generator,
        media_type="text/event-stream",
        headers={
            "Content-Type": "text/event-stream",
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"  # Disable nginx buffering for real-time streaming
        }
    )


@router.get("/quota", response_model=AIQuotaResponse, status_code=status.HTTP_200_OK)
async def get_my_ai_quota(
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    redis: aioredis.Redis = Depends(get_redis_client)
):
    """
    Retrieve active user message and concurrent thread quotas.
    Calculates detailed balances.
    """
    # Verify/load active subscription
    limits = await QuotaService.get_active_subscription_limits(current_user.id, db, redis)
    
    # Check current period message usages
    allowed, details = await QuotaService.check_quota(current_user.id, "messages", 1, db, redis)
    
    # Fetch total concurrent active conversations
    conv_result = await db.execute(
        select(func.count(Conversation.id))
        .where(Conversation.user_id == current_user.id)
        .where(Conversation.status == "active")
    )
    active_threads_count = conv_result.scalar() or 0
    
    return AIQuotaResponse(
        can_send=allowed,
        daily_messages_used=details.get("daily_used", details.get("used", 0) if details.get("limit_type") == "daily" else 0),
        daily_messages_limit=limits.get("messages_per_day", 5),
        monthly_messages_used=details.get("monthly_used", details.get("used", 0) if details.get("limit_type") == "monthly" else 0),
        monthly_messages_limit=limits.get("messages_per_month", 50),
        daily_remaining=details.get("daily_remaining", 0) if details.get("allowed") else details.get("remaining", 0),
        monthly_remaining=details.get("monthly_remaining", 0) if details.get("allowed") else details.get("remaining", 0),
        active_conversations=active_threads_count,
        max_active_conversations=limits.get("max_active_conversations", 1),
        plan_name=limits.get("plan_name", "free"),
        next_daily_reset=None  # Standard reset runs at UTC midnight, can be mapped from worker configs
    )


@router.get("/history", response_model=List[AIHistoryItem], status_code=status.HTTP_200_OK)
async def get_ai_queries_history(
    current_user: CurrentUser = Depends(get_current_user),
    pagination: PaginationParams = Depends(get_pagination),
    db: AsyncSession = Depends(get_db)
):
    """
    Retrieve historical logs of user AI Queries.
    """
    offset = (pagination.page - 1) * pagination.page_size
    stmt = (
        select(AIQuery)
        .where(AIQuery.user_id == current_user.id)
        .order_by(desc(AIQuery.created_at))
        .offset(offset)
        .limit(pagination.page_size)
    )
    result = await db.execute(stmt)
    queries = result.scalars().all()
    return queries
