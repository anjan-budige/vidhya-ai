import uuid
from datetime import datetime, timezone
from typing import List

import redis.asyncio as aioredis
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import (
    get_db,
    get_current_admin,
    get_redis_client,
    require_billing_enabled,
    require_superadmin,
    require_admin_or_above,
)
from app.services.ai_providers import AIConfigError, AIProviderService
from app.services.platform import FREE, PlatformConfigService
from app.models.plan import Plan
from app.schemas.plan import (
    PlanCreateRequest,
    PlanUpdateRequest,
    PlanResponse,
    PlanPublicResponse,
)
from app.models.subscription import UserSubscription
from app.redis_client import RedisKeys
from app.models.audit_log import AuditLog
from app.schemas.auth import CurrentAdmin

router = APIRouter(prefix="/plans", tags=["Subscription Plans"])


async def _validate_context_limits(
    max_context_tokens: int,
    max_response_tokens: int,
    db: AsyncSession,
    redis: aioredis.Redis,
) -> None:
    """A plan must fit inside the currently selected chat model's window."""
    try:
        chat = await AIProviderService.get_default(db, redis, "chat")
    except AIConfigError:
        return  # No provider configured yet; validated once one exists.

    if max_response_tokens > chat.max_output_tokens:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Response limit ({max_response_tokens}) exceeds the selected chat "
                f"model's maximum output ({chat.max_output_tokens}, {chat.model}). "
                "Raise the model's output limit or lower the plan."
            ),
        )

    available = chat.context_window - max_response_tokens - 128
    if max_context_tokens > available:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Context limit exceeds the selected chat model ({chat.model}, "
                f"{chat.context_window} tokens). Maximum input is {max(0, available)} tokens "
                f"after reserving {max_response_tokens} for the response."
            ),
        )


@router.get("/", response_model=List[PlanPublicResponse], status_code=status.HTTP_200_OK)
async def list_public_plans(
    db: AsyncSession = Depends(get_db),
    redis: aioredis.Redis = Depends(get_redis_client),
):
    """
    List public plans. In Free mode the free plan is the only plan.
    Does not require authentication.
    """
    mode = await PlatformConfigService.get_mode(db, redis)
    query = select(Plan).where(Plan.is_active.is_(True))
    if mode == FREE:
        query = query.where(Plan.name == FREE)
    result = await db.execute(query.order_by(Plan.price_inr.asc()))
    return result.scalars().all()


@router.get("/all", response_model=List[PlanResponse], status_code=status.HTTP_200_OK)
async def list_all_plans(
    current_admin: CurrentAdmin = Depends(require_admin_or_above),
    db: AsyncSession = Depends(get_db),
    redis: aioredis.Redis = Depends(get_redis_client),
):
    """
    List plans for the admin UI. In Free mode only the free plan is shown —
    paid plans are disabled and hidden from every surface.
    """
    mode = await PlatformConfigService.get_mode(db, redis)
    query = select(Plan)
    if mode == FREE:
        query = query.where(Plan.name == FREE)
    result = await db.execute(query.order_by(Plan.price_inr.asc()))
    return result.scalars().all()


@router.get("/{plan_id}", response_model=PlanResponse, status_code=status.HTTP_200_OK)
async def get_plan_details(
    plan_id: uuid.UUID,
    current_admin: CurrentAdmin = Depends(require_admin_or_above),
    db: AsyncSession = Depends(get_db)
):
    """
    Retrieve specific plan details by ID (Admin only).
    """
    result = await db.execute(select(Plan).where(Plan.id == plan_id))
    plan = result.scalar_one_or_none()
    
    if not plan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Plan not found."
        )
    return plan


@router.post("/", response_model=PlanResponse, status_code=status.HTTP_201_CREATED)
async def create_plan(
    payload: PlanCreateRequest,
    current_admin: CurrentAdmin = Depends(require_superadmin),
    db: AsyncSession = Depends(get_db),
    redis: aioredis.Redis = Depends(get_redis_client),
    _billing_enabled: None = Depends(require_billing_enabled),
):
    """
    Create a new subscription plan tier (Superadmin only).
    """
    await _validate_context_limits(
        payload.max_context_tokens, payload.max_response_tokens, db, redis
    )

    name_check = await db.execute(select(Plan).where(Plan.name == payload.name))
    if name_check.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Plan tier name '{payload.name}' already exists."
        )
        
    plan = Plan(
        name=payload.name,
        display_name=payload.display_name,
        description=payload.description,
        price_inr=payload.price_inr,
        validity_days=payload.validity_days,
        messages_per_day=payload.messages_per_day,
        messages_per_month=payload.messages_per_month,
        max_sessions=payload.max_sessions,
        max_context_tokens=payload.max_context_tokens,
        max_response_tokens=payload.max_response_tokens,
        memory_retention_days=payload.memory_retention_days,
        summary_frequency=payload.summary_frequency,
        long_term_memory_enabled=payload.long_term_memory_enabled,
        features=payload.features.model_dump()
    )
    
    db.add(plan)
    await db.flush()
    await db.commit()
    return plan


@router.put("/{plan_id}", response_model=PlanResponse, status_code=status.HTTP_200_OK)
async def update_plan(
    plan_id: uuid.UUID,
    payload: PlanUpdateRequest,
    current_admin: CurrentAdmin = Depends(require_superadmin),
    db: AsyncSession = Depends(get_db),
    redis: aioredis.Redis = Depends(get_redis_client),
):
    """
    Update plan configuration snapshot (Superadmin only).
    In Free mode only the free plan may be edited — it is the platform's limits.
    """
    mode = await PlatformConfigService.get_mode_fresh(db)

    result = await db.execute(select(Plan).where(Plan.id == plan_id))
    plan = result.scalar_one_or_none()
    
    if not plan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Plan not found."
        )

    if mode == FREE and plan.name != FREE:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the free plan can be edited while the platform is in Free mode.",
        )

    update_data = payload.model_dump(exclude_unset=True)
    if "features" in update_data and update_data["features"]:
        update_data["features"] = update_data["features"].model_dump()

    if plan.name == FREE and update_data.get("is_active") is False:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The free plan cannot be deactivated — it is required in both modes.",
        )

    if plan.name == FREE and update_data.get("price_inr", 0) != 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The free plan price must remain 0.",
        )

    await _validate_context_limits(
        update_data.get("max_context_tokens", plan.max_context_tokens),
        update_data.get("max_response_tokens", plan.max_response_tokens),
        db,
        redis,
    )

    for key, val in update_data.items():
        setattr(plan, key, val)
        
    plan.updated_at = datetime.now(timezone.utc)

    # Apply the new limits to everyone already on this plan. Otherwise
    # existing subscriptions keep their old frozen snapshot.
    active_user_ids = (
        await db.execute(
            select(UserSubscription.user_id).where(
                UserSubscription.plan_id == plan.id,
                UserSubscription.status == "active",
            )
        )
    ).scalars().all()
    if active_user_ids:
        await db.execute(
            update(UserSubscription)
            .where(
                UserSubscription.plan_id == plan.id,
                UserSubscription.status == "active",
            )
            .values(plan_snapshot=plan.to_snapshot())
        )

    db.add(AuditLog(
        admin_id=current_admin.id,
        action="plan.updated",
        resource_type="plan",
        resource_id=plan.id,
        details={"updates": list(update_data.keys())}
    ))
    
    await db.commit()

    if active_user_ids:
        async with redis.pipeline() as pipe:
            for user_id in active_user_ids:
                pipe.delete(RedisKeys.subscription_cache(str(user_id)))
            await pipe.execute()

    if plan.name == FREE:
        # Free mode limits are served from this row.
        await PlatformConfigService.invalidate_caches(redis)

    await db.refresh(plan)
    return plan


@router.delete("/{plan_id}", status_code=status.HTTP_200_OK)
async def delete_plan(
    plan_id: uuid.UUID,
    current_admin: CurrentAdmin = Depends(require_superadmin),
    db: AsyncSession = Depends(get_db)
):
    """
    Hard delete a subscription plan tier (Superadmin only).
    Will fail if users are currently subscribed to this plan.
    """
    mode = await PlatformConfigService.get_mode_fresh(db)
    if mode == FREE:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Plans cannot be deleted while the platform is in Free mode.",
        )

    result = await db.execute(select(Plan).where(Plan.id == plan_id))
    plan = result.scalar_one_or_none()
    
    if not plan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Plan not found."
        )
        
    if plan.name == "free":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete the default 'free' tier plan."
        )
        
    sub_check = await db.execute(
        select(UserSubscription).where(UserSubscription.plan_id == plan.id)
    )
    if sub_check.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete plan because there are users currently subscribed or historically linked to it."
        )
        
    await db.execute(delete(Plan).where(Plan.id == plan_id))
    
    db.add(AuditLog(
        admin_id=current_admin.id,
        action="plan.deleted",
        resource_type="plan",
        resource_id=plan_id,
        details={"name": plan.name}
    ))
    
    await db.commit()
    
    return {"detail": f"Plan tier '{plan.name}' deleted successfully."}
