import re
import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, func, desc, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

import redis.asyncio as aioredis
from app.dependencies import (
    get_db,
    get_redis_client,
    get_current_user,
    require_admin_or_above,
    require_superadmin,
)
from app.services.api_keys import ApiKeyService
from app.services.quota import QuotaService
from app.services.web_auth import EMAIL_RE, WebAuthService, _normalise, _split_name
from app.models.user import User
from app.models.user_api_key import UserApiKey
from app.models.subscription import UserSubscription
from app.models.plan import Plan
from app.models.payment import PaymentOrder
from app.models.message import Message
from app.models.ai_query import AIQuery
from app.models.conversation import Conversation
from app.models.usage_tracking import UsageTracking
from app.models.audit_log import AuditLog
from app.schemas.auth import CurrentAdmin, CurrentUser
from app.schemas.user import (
    AdminCreateUserRequest,
    AdminCreateUserResponse,
    AdminUpdateUserRequest,
    ApiKeyGenerated,
    ApiKeyInfo,
    ApiKeyUpdateRequest,
    UserBanRequest,
    UserListResponse,
    UserResponse,
)

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
    query = select(User).order_by(desc(User.created_at)).offset(skip).limit(limit)
    
    if search:
        search_term = f"%{search}%"
        query = query.where(
            (User.first_name.ilike(search_term))
            | (User.last_name.ilike(search_term))
            | (User.telegram_username.ilike(search_term))
            | (User.username.ilike(search_term))
            | (User.email.ilike(search_term))
            | (User.mobile.ilike(search_term))
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
        active_sub = next((sub for sub in user.subscriptions if sub.is_active), None)
        current_plan = active_sub.plan.name if active_sub and active_sub.plan else "free"
        
        # Message count (In production, use aggregate queries for scale. This is fine for now.)
        total_messages = len(user.messages) if user.messages else 0
        
        response_list.append(UserListResponse(
            id=user.id,
            telegram_id=user.telegram_id,
            telegram_username=user.telegram_username,
            username=user.username,
            email=user.email,
            mobile=user.mobile,
            auth_provider=user.auth_provider,
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


def _key_info(key: UserApiKey) -> ApiKeyInfo:
    return ApiKeyInfo(
        id=key.id,
        label=key.label,
        key_prefix=key.key_prefix,
        is_enabled=key.is_enabled,
        last_used_at=key.last_used_at,
        revoked_at=key.revoked_at,
        created_at=key.created_at,
    )


@router.post("/", response_model=AdminCreateUserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(
    payload: AdminCreateUserRequest,
    current_admin: CurrentAdmin = Depends(require_admin_or_above),
    db: AsyncSession = Depends(get_db),
    redis: aioredis.Redis = Depends(get_redis_client),
):
    """Create a user from the admin dashboard. API keys are created later."""
    user, setup_sent = await WebAuthService.create_user_by_admin(db, redis, payload)

    db.add(
        AuditLog(
            admin_id=current_admin.id,
            action="user.created",
            resource_type="user",
            resource_id=user.id,
            details={
                "username": user.username,
                "auth_provider": user.auth_provider,
                "setup_email_sent": setup_sent,
            },
        )
    )
    await db.commit()
    await db.refresh(user)

    return AdminCreateUserResponse(
        user=UserResponse.model_validate(user),
        setup_email_sent=setup_sent,
    )



@router.get("/me/api-key", response_model=Optional[ApiKeyInfo], status_code=status.HTTP_200_OK)
async def get_my_api_key(
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    key = await ApiKeyService.get_active_key(db, current_user.id)
    return _key_info(key) if key else None


@router.post("/me/api-key", response_model=ApiKeyGenerated, status_code=status.HTTP_201_CREATED)
async def rotate_my_api_key(
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    redis: aioredis.Redis = Depends(get_redis_client),
):
    """Create or rotate the caller's API key. The plaintext is returned once."""
    raw, key = await ApiKeyService.rotate(db, current_user.id, redis=redis)
    await db.commit()
    return ApiKeyGenerated(key=raw, info=_key_info(key))


@router.patch("/me/api-key", response_model=ApiKeyInfo, status_code=status.HTTP_200_OK)
async def update_my_api_key(
    payload: ApiKeyUpdateRequest,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    redis: aioredis.Redis = Depends(get_redis_client),
):
    if payload.is_enabled is None:
        raise HTTPException(400, "Provide is_enabled.")
    key = await ApiKeyService.set_enabled(
        db, current_user.id, payload.is_enabled, redis=redis
    )
    await db.commit()
    return _key_info(key)


@router.delete("/me/api-key", status_code=status.HTTP_200_OK)
async def revoke_my_api_key(
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    redis: aioredis.Redis = Depends(get_redis_client),
):
    count = await ApiKeyService.revoke(db, current_user.id, redis=redis)
    await db.commit()
    return {"status": "revoked", "keys_revoked": count}



@router.get("/{user_id}/api-key", response_model=Optional[ApiKeyInfo], status_code=status.HTTP_200_OK)
async def admin_get_user_api_key(
    user_id: uuid.UUID,
    current_admin: CurrentAdmin = Depends(require_admin_or_above),
    db: AsyncSession = Depends(get_db),
):
    key = await ApiKeyService.get_active_key(db, user_id)
    return _key_info(key) if key else None


@router.post("/{user_id}/api-key", response_model=ApiKeyGenerated, status_code=status.HTTP_201_CREATED)
async def admin_rotate_user_api_key(
    user_id: uuid.UUID,
    current_admin: CurrentAdmin = Depends(require_admin_or_above),
    db: AsyncSession = Depends(get_db),
    redis: aioredis.Redis = Depends(get_redis_client),
):
    user = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if not user:
        raise HTTPException(404, "User not found.")

    raw, key = await ApiKeyService.rotate(
        db, user_id, created_by=current_admin.id, redis=redis
    )
    db.add(
        AuditLog(
            admin_id=current_admin.id,
            action="user.api_key_rotated",
            resource_type="user",
            resource_id=user_id,
            details={"key_prefix": key.key_prefix},
        )
    )
    await db.commit()
    return ApiKeyGenerated(key=raw, info=_key_info(key))


@router.patch("/{user_id}/api-key", response_model=ApiKeyInfo, status_code=status.HTTP_200_OK)
async def admin_update_user_api_key(
    user_id: uuid.UUID,
    payload: ApiKeyUpdateRequest,
    current_admin: CurrentAdmin = Depends(require_admin_or_above),
    db: AsyncSession = Depends(get_db),
    redis: aioredis.Redis = Depends(get_redis_client),
):
    if payload.is_enabled is None:
        raise HTTPException(400, "Provide is_enabled.")
    key = await ApiKeyService.set_enabled(
        db, user_id, payload.is_enabled, redis=redis
    )
    db.add(
        AuditLog(
            admin_id=current_admin.id,
            action="user.api_key_toggled",
            resource_type="user",
            resource_id=user_id,
            details={"is_enabled": payload.is_enabled},
        )
    )
    await db.commit()
    return _key_info(key)


@router.delete("/{user_id}/api-key", status_code=status.HTTP_200_OK)
async def admin_revoke_user_api_key(
    user_id: uuid.UUID,
    current_admin: CurrentAdmin = Depends(require_admin_or_above),
    db: AsyncSession = Depends(get_db),
    redis: aioredis.Redis = Depends(get_redis_client),
):
    count = await ApiKeyService.revoke(db, user_id, redis=redis)
    db.add(
        AuditLog(
            admin_id=current_admin.id,
            action="user.api_key_revoked",
            resource_type="user",
            resource_id=user_id,
            details={"keys_revoked": count},
        )
    )
    await db.commit()
    return {"status": "revoked", "keys_revoked": count}


@router.put("/{user_id}/status", response_model=UserResponse, status_code=status.HTTP_200_OK)
async def update_user_status(
    user_id: uuid.UUID,
    payload: UserBanRequest,
    current_admin: CurrentAdmin = Depends(require_admin_or_above),
    db: AsyncSession = Depends(get_db),
    redis: aioredis.Redis = Depends(get_redis_client),
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
        await WebAuthService.revoke_user_sessions(
            db, redis, user.id, revoke_api_keys=True
        )
        await ApiKeyService.clear_bot_binding(db, redis, user.id)
    
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


@router.patch("/{user_id}", response_model=UserResponse, status_code=status.HTTP_200_OK)
async def admin_update_user(
    user_id: uuid.UUID,
    payload: AdminUpdateUserRequest,
    current_admin: CurrentAdmin = Depends(require_superadmin),
    db: AsyncSession = Depends(get_db),
):
    """Edit a user's profile details."""
    user = (
        await db.execute(select(User).where(User.id == user_id))
    ).scalar_one_or_none()
    if not user:
        raise HTTPException(404, "User not found.")

    data = payload.model_dump(exclude_unset=True)
    changes = []

    if data.get("name") is not None:
        first_name, last_name = _split_name(data["name"])
        user.first_name = first_name
        user.last_name = last_name
        changes.append("name")

    if data.get("username") is not None:
        username = _normalise(data["username"])
        if not re.fullmatch(r"[a-z0-9_]{3,30}", username):
            raise HTTPException(400, "Username must be 3-30 lowercase letters, numbers or underscore.")
        taken = (
            await db.execute(
                select(User.id).where(User.username == username, User.id != user.id)
            )
        ).scalar_one_or_none()
        if taken:
            raise HTTPException(409, "That username is already taken.")
        user.username = username
        changes.append("username")

    if data.get("email") is not None:
        email = _normalise(data["email"])
        if not EMAIL_RE.match(email):
            raise HTTPException(400, "Enter a valid email address.")
        taken = (
            await db.execute(
                select(User.id).where(User.email == email, User.id != user.id)
            )
        ).scalar_one_or_none()
        if taken:
            raise HTTPException(409, "That email is already in use.")
        user.email = email
        changes.append("email")

    if data.get("mobile") is not None:
        mobile = re.sub(r"[\s-]+", "", data["mobile"])
        taken = (
            await db.execute(
                select(User.id).where(User.mobile == mobile, User.id != user.id)
            )
        ).scalar_one_or_none()
        if taken:
            raise HTTPException(409, "That mobile number is already in use.")
        user.mobile = mobile
        changes.append("mobile")

    db.add(
        AuditLog(
            admin_id=current_admin.id,
            action="user.updated",
            resource_type="user",
            resource_id=user.id,
            details={"fields": changes},
        )
    )
    await db.commit()
    await db.refresh(user)
    return user


@router.delete("/{user_id}", status_code=status.HTTP_200_OK)
async def admin_delete_user(
    user_id: uuid.UUID,
    current_admin: CurrentAdmin = Depends(require_superadmin),
    db: AsyncSession = Depends(get_db),
    redis: aioredis.Redis = Depends(get_redis_client),
):
    """Permanently delete a user and all of their data."""
    user = (
        await db.execute(select(User).where(User.id == user_id))
    ).scalar_one_or_none()
    if not user:
        raise HTTPException(404, "User not found.")

    username = user.username
    email = user.email
    key_hashes = (
        await db.execute(
            select(UserApiKey.key_hash).where(UserApiKey.user_id == user.id)
        )
    ).scalars().all()

    # Invalidate Redis state before deleting rows.
    await ApiKeyService.clear_bot_binding(db, redis, user.id)
    for key_hash in key_hashes:
        await redis.delete(f"apikey:{key_hash}")
    for pattern in (
        f"quota:daily:{user.id}:*",
        f"quota:monthly:{user.id}:*",
        f"sub_cache:{user.id}",
        f"bot:binding:{user.id}",
    ):
        async for key in redis.scan_iter(match=pattern, count=200):
            await redis.delete(key)

    await db.execute(delete(Message).where(Message.user_id == user.id))
    await db.execute(delete(AIQuery).where(AIQuery.user_id == user.id))
    await db.execute(delete(Conversation).where(Conversation.user_id == user.id))
    await db.execute(delete(UsageTracking).where(UsageTracking.user_id == user.id))
    await db.execute(delete(UserSubscription).where(UserSubscription.user_id == user.id))
    await db.execute(delete(UserApiKey).where(UserApiKey.user_id == user.id))

    db.add(
        AuditLog(
            admin_id=current_admin.id,
            action="user.deleted",
            resource_type="user",
            resource_id=user.id,
            details={"username": username, "email": email},
        )
    )
    await db.execute(delete(User).where(User.id == user.id))
    await db.commit()
    return {"status": "deleted"}


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
        selectinload(User.payment_orders).selectinload(PaymentOrder.plan),
        selectinload(User.conversations)
    )
    result = await db.execute(query)
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
        
    active_sub = next((sub for sub in user.subscriptions if sub.is_active), None)
    
    all_payments = []
    for p in user.payment_orders:
        all_payments.append({
            "id": p.id,
            "amount": p.amount_rupees,
            "status": p.status,
            "provider_transaction_id": p.provider_payment_id or p.order_ref,
            "created_at": p.created_at,
            "plan_name": p.plan_name or (p.plan.name if p.plan else "unknown")
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
        "username": user.username,
        "email": user.email,
        "mobile": user.mobile,
        "auth_provider": user.auth_provider,
        "email_verified": bool(user.email_verified_at),
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
