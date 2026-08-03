"""
╔══════════════════════════════════════════════════════════════════╗
║  VIDHYA BOT — Subscriptions Router                               ║
║  Provides: User subscription details, free tier activations,     ║
║  and admin-only user monitoring checks.                          ║
╚══════════════════════════════════════════════════════════════════╝
"""

import uuid
from datetime import date, datetime, timezone
from typing import List

import redis.asyncio as aioredis
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import (
    get_db,
    get_redis_client,
    get_current_user,
    get_current_admin,
    require_admin_or_above
)
from app.models.subscription import UserSubscription
from app.models.conversation import Conversation
from app.models.usage_tracking import UsageTracking
from app.models.user import User
from app.models.audit_log import AuditLog
from app.services.subscription import SubscriptionService
from app.services.quota import QuotaService
from app.schemas.subscription import (
    SubscriptionResponse,
    SubscriptionWithUsage,
    SubscriptionAdminResponse,
    AssignPlanRequest
)
from app.schemas.auth import CurrentUser, CurrentAdmin

router = APIRouter(prefix="/subscriptions", tags=["Subscriptions"])


@router.get("/me", response_model=SubscriptionWithUsage, status_code=status.HTTP_200_OK)
async def get_my_subscription(
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    redis: aioredis.Redis = Depends(get_redis_client)
):
    """
    Retrieve current user's active subscription, including cached and DB quotas.
    If no active subscription exists, automatically triggers Free plan activation.
    """
    # 1. Retrieve active subscription
    result = await db.execute(
        select(UserSubscription)
        .where(UserSubscription.user_id == current_user.id)
        .where(UserSubscription.status == "active")
    )
    sub = result.scalar_one_or_none()
    
    if not sub:
        # Auto-provision "Free" plan
        sub = await SubscriptionService.activate_free_plan(current_user.id, db, redis)
        await db.commit()
        
    # 2. Get active limits
    limits = sub.plan_snapshot
    
    # 3. Read current period message usage (Quota checks)
    today = date.today()
    today_str = today.strftime("%Y-%m-%d")
    month_str = today.strftime("%Y-%m")
    
    # Fast path check on Redis daily counter
    from app.redis_client import RedisKeys
    daily_key = RedisKeys.quota_daily(str(current_user.id), today_str)
    daily_val = await redis.get(daily_key)
    if daily_val is not None:
        daily_used = int(daily_val)
    else:
        # Fallback to DB
        db_result = await db.execute(
            select(UsageTracking)
            .where(UsageTracking.user_id == current_user.id)
            .where(UsageTracking.period_type == "daily")
            .where(UsageTracking.period_date == today)
        )
        db_record = db_result.scalar_one_or_none()
        daily_used = db_record.messages_used if db_record else 0
        
    # Fast path check on Redis monthly counter
    monthly_key = RedisKeys.quota_monthly(str(current_user.id), month_str)
    monthly_val = await redis.get(monthly_key)
    if monthly_val is not None:
        monthly_used = int(monthly_val)
    else:
        # Fallback to DB
        first_of_month = today.replace(day=1)
        db_result = await db.execute(
            select(UsageTracking)
            .where(UsageTracking.user_id == current_user.id)
            .where(UsageTracking.period_type == "monthly")
            .where(UsageTracking.period_date == first_of_month)
        )
        db_record = db_result.scalar_one_or_none()
        monthly_used = db_record.messages_used if db_record else 0
        
    # 4. Count active conversations
    conv_result = await db.execute(
        select(func.count(Conversation.id))
        .where(Conversation.user_id == current_user.id)
        .where(Conversation.status == "active")
    )
    active_conversations_count = conv_result.scalar() or 0
    
    return SubscriptionWithUsage(
        id=sub.id,
        user_id=sub.user_id,
        plan_id=sub.plan_id,
        status=sub.status,
        started_at=sub.started_at,
        expires_at=sub.expires_at,
        plan_snapshot=sub.plan_snapshot,
        total_messages_used=sub.total_messages_used,
        total_tokens_consumed=sub.total_tokens_consumed,
        total_conversations=sub.total_conversations,
        created_at=sub.created_at,
        updated_at=sub.updated_at,
        
        daily_messages_used=daily_used,
        daily_messages_limit=limits.get("messages_per_day", 5),
        monthly_messages_used=monthly_used,
        monthly_messages_limit=limits.get("messages_per_month", 50),
        active_conversations=active_conversations_count,
        max_active_conversations=limits.get("max_active_conversations", 1),
        plan_name=limits.get("plan_name", "free"),
        plan_display_name=limits.get("display_name", "Free Plan")
    )


@router.post("/free/activate", response_model=SubscriptionResponse, status_code=status.HTTP_201_CREATED)
async def activate_free_tier(
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    redis: aioredis.Redis = Depends(get_redis_client)
):
    """
    Manually activate the default free plan tier.
    Valid only if the user has no existing active subscriptions.
    """
    # Check if user already has an active subscription
    check_result = await db.execute(
        select(UserSubscription)
        .where(UserSubscription.user_id == current_user.id)
        .where(UserSubscription.status == "active")
    )
    active_sub = check_result.scalar_one_or_none()
    if active_sub and active_sub.plan_snapshot.get("plan_name") != "free":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot activate free plan while a paid tier subscription is active."
        )
    elif active_sub:
        return active_sub  # Already active on free, return it
        
    sub = await SubscriptionService.activate_free_plan(current_user.id, db, redis)
    await db.commit()
    return sub


@router.get("/user/{user_id}", response_model=SubscriptionAdminResponse, status_code=status.HTTP_200_OK)
async def get_user_subscription_admin(
    user_id: uuid.UUID,
    current_admin: CurrentAdmin = Depends(require_admin_or_above),
    db: AsyncSession = Depends(get_db)
):
    """
    Retrieve specific user active subscription limits (Admin only).
    """
    # Verify user exists
    user_check = await db.execute(select(User).where(User.id == user_id))
    user = user_check.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")
        
    result = await db.execute(
        select(UserSubscription)
        .where(UserSubscription.user_id == user_id)
        .where(UserSubscription.status == "active")
    )
    sub = result.scalar_one_or_none()
    
    if not sub:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User has no active subscription."
        )
        
    return SubscriptionAdminResponse(
        id=sub.id,
        user_id=sub.user_id,
        plan_id=sub.plan_id,
        status=sub.status,
        started_at=sub.started_at,
        expires_at=sub.expires_at,
        plan_snapshot=sub.plan_snapshot,
        total_messages_used=sub.total_messages_used,
        total_tokens_consumed=sub.total_tokens_consumed,
        total_conversations=sub.total_conversations,
        created_at=sub.created_at,
        updated_at=sub.updated_at,
        
        user_telegram_id=user.telegram_id,
        user_first_name=user.first_name,
        plan_name=sub.plan_snapshot.get("plan_name")
    )


@router.post("/admin/assign", response_model=SubscriptionResponse, status_code=status.HTTP_200_OK)
async def admin_assign_subscription(
    payload: AssignPlanRequest,
    current_admin: CurrentAdmin = Depends(require_admin_or_above),
    db: AsyncSession = Depends(get_db),
    redis: aioredis.Redis = Depends(get_redis_client)
):
    """
    Manually assign a plan to a user (Admin only).
    """
    sub = await SubscriptionService.admin_assign_plan(
        user_id=payload.user_id,
        plan_id=payload.plan_id,
        db=db,
        redis=redis
    )
    
    # Audit Logging
    db.add(AuditLog(
        admin_id=current_admin.id,
        action="subscription.assigned",
        resource_type="subscription",
        resource_id=sub.id,
        details={"user_id": str(payload.user_id), "plan_id": str(payload.plan_id)}
    ))
    
    await db.commit()
    return sub
