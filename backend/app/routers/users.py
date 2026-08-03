"""
╔══════════════════════════════════════════════════════════════════╗
║  VIDHYA BOT — Users Router                                       ║
║  Provides: Admin endpoints to list users, and ban/unban them.    ║
╚══════════════════════════════════════════════════════════════════╝
"""

import uuid
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

import redis.asyncio as aioredis
from app.dependencies import get_db, require_admin_or_above, get_redis_client
from app.services.quota import QuotaService
from app.models.user import User
from app.models.subscription import UserSubscription
from app.models.plan import Plan
from app.models.payment import Payment
from app.models.message import Message
from app.models.audit_log import AuditLog
from app.schemas.auth import CurrentAdmin
from app.schemas.user import UserListResponse, UserBanRequest, UserResponse

router = APIRouter(prefix="/users", tags=["Users"])


@router.get("/", response_model=List[UserListResponse], status_code=status.HTTP_200_OK)
async def list_users(
    skip: int = 0,
    limit: int = 100,
    search: str = None,
    current_admin: CurrentAdmin = Depends(require_admin_or_above),
    db: AsyncSession = Depends(get_db)
):
    """
    List all registered Telegram users (Admin only).
    Includes their current plan (if active) and total message count.
    """
    # Build query
    query = select(User).order_by(desc(User.created_at)).offset(skip).limit(limit)
    
    # Optional search by name or telegram_username
    if search:
        search_term = f"%{search}%"
        query = query.where(
            (User.first_name.ilike(search_term)) | 
            (User.last_name.ilike(search_term)) | 
            (User.telegram_username.ilike(search_term))
        )
        
    # We use selectinload to eagerly load subscriptions and messages if we want,
    # but for aggregation it's better to fetch users then do a subquery or secondary queries.
    # For simplicity and performance on a small dataset, we'll load the user and their active sub.
    query = query.options(
        selectinload(User.subscriptions).selectinload(UserSubscription.plan),
        selectinload(User.messages)
    )
    
    result = await db.execute(query)
    users = result.scalars().all()
    
    response_list = []
    for user in users:
        # Determine current plan
        active_sub = next((sub for sub in user.subscriptions if sub.is_active), None)
        current_plan = active_sub.plan.name if active_sub and active_sub.plan else "free"
        
        # Message count (In production, use aggregate queries for scale. This is fine for now.)
        total_messages = len(user.messages) if user.messages else 0
        
        response_list.append(UserListResponse(
            id=user.id,
            telegram_id=user.telegram_id,
            telegram_username=user.telegram_username,
            first_name=user.first_name,
            last_name=user.last_name,
            is_active=user.is_active,
            is_banned=user.is_banned,
            current_plan=current_plan,
            total_messages=total_messages,
            last_login_at=user.last_login_at,
            created_at=user.created_at
        ))
        
    return response_list


@router.put("/{user_id}/status", response_model=UserResponse, status_code=status.HTTP_200_OK)
async def update_user_status(
    user_id: uuid.UUID,
    payload: UserBanRequest,
    current_admin: CurrentAdmin = Depends(require_admin_or_above),
    db: AsyncSession = Depends(get_db)
):
    """
    Ban or unban a user. (Admin only).
    If reason is 'unban', it unbans the user.
    """
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found."
        )
        
    if payload.reason.lower() == 'unban':
        user.is_banned = False
        user.ban_reason = None
        action_type = "user.unbanned"
    else:
        user.is_banned = True
        user.ban_reason = payload.reason
        action_type = "user.banned"
    
    # Audit Logging
    db.add(AuditLog(
        admin_id=current_admin.id,
        action=action_type,
        resource_type="user",
        resource_id=user.id,
        details={"reason": payload.reason}
    ))
    
    await db.commit()
    await db.refresh(user)
    
    return user


@router.get("/{user_id}/details", status_code=status.HTTP_200_OK)
async def get_user_detailed_info(
    user_id: uuid.UUID,
    current_admin: CurrentAdmin = Depends(require_admin_or_above),
    db: AsyncSession = Depends(get_db),
    redis: aioredis.Redis = Depends(get_redis_client)
):
    """
    Get comprehensive details for a specific user (Admin only).
    """
    query = select(User).where(User.id == user_id).options(
        selectinload(User.subscriptions).selectinload(UserSubscription.plan),
        selectinload(User.payments).selectinload(Payment.plan),
        selectinload(User.conversations)
    )
    result = await db.execute(query)
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
        
    active_sub = next((sub for sub in user.subscriptions if sub.is_active), None)
    
    all_payments = []
    for p in user.payments:
        all_payments.append({
            "id": p.id,
            "amount": p.amount_rupees,
            "status": p.status,
            "provider_transaction_id": p.merchant_txn_id,
            "created_at": p.created_at,
            "plan_name": p.plan.name if p.plan else "unknown"
        })
    all_payments.sort(key=lambda x: x["created_at"], reverse=True)
    
    msg_counts_result = await db.execute(
        select(Message.conversation_id, Message.role, func.count(Message.id))
        .where(Message.user_id == user_id)
        .group_by(Message.conversation_id, Message.role)
    )
    
    conv_msg_breakdown = {}
    for cid, role, count in msg_counts_result.all():
        if cid not in conv_msg_breakdown:
            conv_msg_breakdown[cid] = {"user": 0, "agent": 0}
        
        if role == "user":
            conv_msg_breakdown[cid]["user"] += count
        else:
            conv_msg_breakdown[cid]["agent"] += count
            
    all_conversations = []
    if user.conversations:
        for c in user.conversations:
            breakdown = conv_msg_breakdown.get(c.id, {"user": 0, "agent": 0})
            all_conversations.append({
                "id": c.id,
                "title": c.title or "Untitled Conversation",
                "total_messages": c.total_messages,
                "user_messages": breakdown["user"],
                "agent_messages": breakdown["agent"],
                "status": c.status,
                "started_at": c.started_at
            })
        all_conversations.sort(key=lambda x: x["started_at"], reverse=True)

    limits = await QuotaService.get_active_subscription_limits(user_id, db, redis)
    _, quota_details = await QuotaService.check_quota(user_id, "messages", 0, db, redis)

    return {
        "id": user.id,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "telegram_id": user.telegram_id,
        "telegram_username": user.telegram_username,
        "is_banned": user.is_banned,
        "created_at": user.created_at,
        "conversations_count": len(user.conversations) if user.conversations else 0,
        "subscription": {
            "plan_name": active_sub.plan.display_name if active_sub and active_sub.plan else "Free Plan",
            "status": active_sub.status if active_sub else "active",
            "current_period_end": active_sub.expires_at if active_sub else None,
            "monthly_messages_used": quota_details.get("monthly_used", 0),
            "monthly_messages_limit": limits.get("messages_per_month", 50),
            "daily_messages_used": quota_details.get("daily_used", 0),
            "daily_messages_limit": limits.get("messages_per_day", 5),
            "validity_days": active_sub.plan.validity_days if active_sub and active_sub.plan else 30,
        },
        "payments": all_payments,
        "conversations": all_conversations
    }
