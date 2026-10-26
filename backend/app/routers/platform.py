"""
Vidhya Bot — Platform Mode Router

Public: exposes the current mode so every client renders the same truth.
Admin:  preflight counts and the paid <-> free transition.
"""

from typing import Literal, Optional

import redis.asyncio as aioredis
from fastapi import APIRouter, Depends, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.dependencies import (
    get_db,
    get_redis_client,
    require_admin_or_above,
    require_superadmin,
)
from app.models.plan import Plan
from app.schemas.auth import CurrentAdmin
from app.services.platform import FREE, PAID, PlatformConfigService

settings = get_settings()

public_router = APIRouter(prefix="/config", tags=["Platform Config"])
admin_router = APIRouter(prefix="/admin/platform", tags=["Admin Platform"])


def _plan_dict(plan: Plan) -> dict:
    return {
        "id": str(plan.id),
        "name": plan.name,
        "display_name": plan.display_name,
        "description": plan.description,
        "price_inr": plan.price_inr,
        "validity_days": plan.validity_days,
        "limits": plan.to_snapshot(),
    }


@public_router.get("/public", status_code=status.HTTP_200_OK)
async def get_public_config(
    db: AsyncSession = Depends(get_db),
    redis: aioredis.Redis = Depends(get_redis_client),
):
    """
    Mode + plans for client rendering. Never used for authorisation —
    the server re-checks the mode on every protected action.
    """
    mode = await PlatformConfigService.get_mode(db, redis)
    free_plan = await PlatformConfigService.get_free_plan(db)

    plans = []
    if mode == PAID:
        result = await db.execute(
            select(Plan)
            .where(Plan.is_active.is_(True), Plan.price_inr > 0)
            .order_by(Plan.price_inr.asc())
        )
        plans = [_plan_dict(p) for p in result.scalars().all()]

    access = await PlatformConfigService.get_access_settings(db, redis)
    bot = await PlatformConfigService.get_bot_settings(db, redis)

    return {
        "platform_mode": mode,
        "billing_enabled": mode == PAID,
        "registration_enabled": access["registration_enabled"],
        "email_otp_login": access["email_otp_login"],
        "register_url": f"{settings.APP_URL}/register",
        "bot": bot,
        "free_plan": _plan_dict(free_plan) if free_plan else None,
        "plans": plans,
    }


@admin_router.get("/status", status_code=status.HTTP_200_OK)
async def get_platform_status(
    current_admin: CurrentAdmin = Depends(require_admin_or_above),
    db: AsyncSession = Depends(get_db),
):
    """Everything the admin UI needs before switching modes."""
    return await PlatformConfigService.preflight(db)


class BotSettingsRequest(BaseModel):
    welcome_title: Optional[str] = None
    welcome_message: Optional[str] = None
    login_hint: Optional[str] = None
    register_hint: Optional[str] = None
    show_register_link: Optional[bool] = None
    session_prompt_text: Optional[str] = None
    session_limit_text: Optional[str] = None
    session_started_text: Optional[str] = None
    idle_prompt_minutes: Optional[int] = None


@admin_router.get("/bot", status_code=status.HTTP_200_OK)
async def get_bot_settings(
    current_admin: CurrentAdmin = Depends(require_admin_or_above),
    db: AsyncSession = Depends(get_db),
    redis: aioredis.Redis = Depends(get_redis_client),
):
    return await PlatformConfigService.get_bot_settings(db, redis)


@admin_router.patch("/bot", status_code=status.HTTP_200_OK)
async def update_bot_settings(
    payload: BotSettingsRequest,
    current_admin: CurrentAdmin = Depends(require_superadmin),
    db: AsyncSession = Depends(get_db),
    redis: aioredis.Redis = Depends(get_redis_client),
):
    return await PlatformConfigService.update_bot_settings(
        db, redis, current_admin.id, payload.model_dump(exclude_unset=True)
    )


class AccessSettingsRequest(BaseModel):
    registration_enabled: Optional[bool] = None
    email_otp_login: Optional[bool] = None


@admin_router.get("/access", status_code=status.HTTP_200_OK)
async def get_access_settings(
    current_admin: CurrentAdmin = Depends(require_admin_or_above),
    db: AsyncSession = Depends(get_db),
    redis: aioredis.Redis = Depends(get_redis_client),
):
    return await PlatformConfigService.get_access_settings(db, redis)


@admin_router.patch("/access", status_code=status.HTTP_200_OK)
async def update_access_settings(
    payload: AccessSettingsRequest,
    current_admin: CurrentAdmin = Depends(require_superadmin),
    db: AsyncSession = Depends(get_db),
    redis: aioredis.Redis = Depends(get_redis_client),
):
    return await PlatformConfigService.update_access_settings(
        db,
        redis,
        current_admin.id,
        registration_enabled=payload.registration_enabled,
        email_otp_login=payload.email_otp_login,
    )


class ModeSwitchRequest(BaseModel):
    mode: Literal["paid", "free"]
    deactivate_plans: bool = False
    cancel_pending_payments: bool = False
    reactivate_plans: bool = False


@admin_router.post("/mode", status_code=status.HTTP_200_OK)
async def switch_platform_mode(
    payload: ModeSwitchRequest,
    current_admin: CurrentAdmin = Depends(require_superadmin),
    db: AsyncSession = Depends(get_db),
    redis: aioredis.Redis = Depends(get_redis_client),
):
    """
    Switch between paid and free mode.

    The client's flags only authorise *bundled* cleanup steps; the mode
    itself is always decided by this server from the current DB state.
    """
    if payload.mode == FREE:
        return await PlatformConfigService.switch_to_free(
            db=db,
            redis=redis,
            admin_id=current_admin.id,
            deactivate_plans=payload.deactivate_plans,
            cancel_pending_payments=payload.cancel_pending_payments,
        )

    return await PlatformConfigService.switch_to_paid(
        db=db,
        redis=redis,
        admin_id=current_admin.id,
        reactivate_plans=payload.reactivate_plans,
    )
