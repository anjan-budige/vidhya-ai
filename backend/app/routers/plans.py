"""
╔══════════════════════════════════════════════════════════════════╗
║  VIDHYA BOT — Plans Router                                       ║
║  Provides: Public plan listings and complete superadmin-only     ║
║  Plan CRUD operations.                                           ║
╚══════════════════════════════════════════════════════════════════╝
"""

import uuid
from datetime import datetime, timezone
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db, get_current_admin, require_superadmin, require_admin_or_above
from app.models.plan import Plan
from app.schemas.plan import (
    PlanCreateRequest,
    PlanUpdateRequest,
    PlanResponse,
    PlanPublicResponse,
)
from app.models.subscription import UserSubscription
from app.models.audit_log import AuditLog
from app.schemas.auth import CurrentAdmin

router = APIRouter(prefix="/plans", tags=["Subscription Plans"])


@router.get("/", response_model=List[PlanPublicResponse], status_code=status.HTTP_200_OK)
async def list_public_plans(db: AsyncSession = Depends(get_db)):
    """
    List all active, public subscription plans available for purchase.
    Does not require authentication.
    """
    result = await db.execute(
        select(Plan).where(Plan.is_active == True).order_by(Plan.price_inr.asc())
    )
    plans = result.scalars().all()
    return plans


@router.get("/all", response_model=List[PlanResponse], status_code=status.HTTP_200_OK)
async def list_all_plans(
    current_admin: CurrentAdmin = Depends(require_admin_or_above),
    db: AsyncSession = Depends(get_db)
):
    """
    List all plans including inactive tiers (Admin only).
    """
    result = await db.execute(
        select(Plan).order_by(Plan.price_inr.asc())
    )
    plans = result.scalars().all()
    return plans


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
    db: AsyncSession = Depends(get_db)
):
    """
    Create a new subscription plan tier (Superadmin only).
    """
    # Check if plan name already exists
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
        max_conversations=payload.max_conversations,
        max_active_conversations=payload.max_active_conversations,
        conversation_timeout_min=payload.conversation_timeout_min,
        max_context_messages=payload.max_context_messages,
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
    db: AsyncSession = Depends(get_db)
):
    """
    Update plan configuration snapshot (Superadmin only).
    """
    result = await db.execute(select(Plan).where(Plan.id == plan_id))
    plan = result.scalar_one_or_none()
    
    if not plan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Plan not found."
        )
        
    update_data = payload.model_dump(exclude_unset=True)
    if "features" in update_data and update_data["features"]:
        update_data["features"] = update_data["features"].model_dump()
        
    for key, val in update_data.items():
        setattr(plan, key, val)
        
    plan.updated_at = datetime.now(timezone.utc)
    
    # Audit Logging
    db.add(AuditLog(
        admin_id=current_admin.id,
        action="plan.updated",
        resource_type="plan",
        resource_id=plan.id,
        details={"updates": list(update_data.keys())}
    ))
    
    await db.commit()
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
        
    # Check for existing active subscriptions
    sub_check = await db.execute(
        select(UserSubscription).where(UserSubscription.plan_id == plan.id)
    )
    if sub_check.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete plan because there are users currently subscribed or historically linked to it."
        )
        
    await db.execute(delete(Plan).where(Plan.id == plan_id))
    
    # Audit Logging
    db.add(AuditLog(
        admin_id=current_admin.id,
        action="plan.deleted",
        resource_type="plan",
        resource_id=plan_id,
        details={"name": plan.name}
    ))
    
    await db.commit()
    
    return {"detail": f"Plan tier '{plan.name}' deleted successfully."}
