"""
Vidhya Bot — Platform Mode Service

Controls whether the deployment runs as a paid product ("paid") or as an
open platform with a single free plan ("free").

In free mode the free plan row is the single source of truth for limits:
every user gets exactly those limits, regardless of any historical plan.
"""

import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import redis.asyncio as aioredis
from fastapi import HTTPException, status
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit_log import AuditLog
from app.models.payment import PaymentOrder
from app.models.plan import Plan
from app.models.platform_setting import PlatformSetting
from app.models.subscription import UserSubscription
from app.services.subscription import get_ist_end_of_day_expiry

logger = logging.getLogger("vidhya.platform")

FREE = "free"
PAID = "paid"

MODE_CACHE_KEY = "platform:mode"
FREE_LIMITS_CACHE_KEY = "platform:free_limits"
ACCESS_CACHE_KEY = "platform:access"
BOT_CACHE_KEY = "platform:bot"
SUB_CACHE_PATTERN = "sub_cache:*"

DEFAULT_BOT_SETTINGS = {
    "welcome_title": "Welcome to Vidhya AI",
    "welcome_message": (
        "Your institution's AI learning assistant. Ask questions from your "
        "course material, notes and training documents — answers stay grounded "
        "in what your organisation has approved."
    ),
    "login_hint": "Use /login <api-key> to connect your account.",
    "register_hint": "No account? Register here: {register_url}",
    "show_register_link": True,
    "session_prompt_text": (
        "You have been away for a while. Continue the previous session or start a new one?"
    ),
    "session_limit_text": (
        "You have reached your session limit. Delete an existing chat to start a new one."
    ),
    "session_started_text": "New session started.",
    "idle_prompt_minutes": 25,
}


def _plan_summary(plan: Optional[Plan]) -> Optional[Dict[str, Any]]:
    if not plan:
        return None
    return {
        "id": str(plan.id),
        "name": plan.name,
        "display_name": plan.display_name,
        "price_inr": plan.price_inr,
        "limits": plan.to_snapshot(),
    }


class PlatformConfigService:
    """Read/write the platform mode and perform the paid <-> free transition."""


    @staticmethod
    async def _get_row(db: AsyncSession) -> PlatformSetting:
        result = await db.execute(
            select(PlatformSetting).where(PlatformSetting.id == 1)
        )
        row = result.scalar_one_or_none()
        if row is None:
            row = PlatformSetting(id=1, platform_mode=PAID)
            db.add(row)
            await db.flush()
        return row

    @classmethod
    async def get_mode(cls, db: AsyncSession, redis: aioredis.Redis) -> str:
        """Cached read — use for display and quota paths."""
        cached = await redis.get(MODE_CACHE_KEY)
        if cached in (PAID, FREE):
            return cached
        mode = await cls.get_mode_fresh(db)
        await redis.set(MODE_CACHE_KEY, mode, ex=60)
        return mode

    @classmethod
    async def get_mode_fresh(cls, db: AsyncSession) -> str:
        """Uncached read — use for write and money paths."""
        row = await cls._get_row(db)
        return row.platform_mode

    @staticmethod
    async def get_free_plan(db: AsyncSession) -> Optional[Plan]:
        result = await db.execute(select(Plan).where(Plan.name == FREE))
        return result.scalar_one_or_none()

    @classmethod
    async def get_free_limits(
        cls, db: AsyncSession, redis: aioredis.Redis
    ) -> Dict[str, Any]:
        """Live limits of the free plan — the platform limits in free mode."""
        cached = await redis.get(FREE_LIMITS_CACHE_KEY)
        if cached:
            try:
                return json.loads(cached)
            except Exception:
                pass

        plan = await cls.get_free_plan(db)
        if not plan:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Free plan is not configured on this platform.",
            )
        snapshot = plan.to_snapshot()
        await redis.set(FREE_LIMITS_CACHE_KEY, json.dumps(snapshot), ex=60)
        return snapshot

    @classmethod
    async def get_access_settings(
        cls, db: AsyncSession, redis: aioredis.Redis
    ) -> Dict[str, Any]:
        cached = await redis.get(ACCESS_CACHE_KEY)
        if cached:
            try:
                return json.loads(cached)
            except Exception:
                pass

        row = await cls._get_row(db)
        data = {
            "registration_enabled": row.registration_enabled,
            "email_otp_login": row.email_otp_login,
        }
        await redis.set(ACCESS_CACHE_KEY, json.dumps(data), ex=60)
        return data

    @classmethod
    async def update_access_settings(
        cls,
        db: AsyncSession,
        redis: aioredis.Redis,
        admin_id,
        registration_enabled: Optional[bool] = None,
        email_otp_login: Optional[bool] = None,
    ) -> Dict[str, Any]:
        row = await cls._get_row(db)
        if registration_enabled is not None:
            row.registration_enabled = registration_enabled
        if email_otp_login is not None:
            row.email_otp_login = email_otp_login

        db.add(
            AuditLog(
                admin_id=admin_id,
                action="platform.access_settings_updated",
                resource_type="platform",
                resource_id=None,
                details={
                    "registration_enabled": row.registration_enabled,
                    "email_otp_login": row.email_otp_login,
                },
            )
        )
        await db.commit()
        await redis.delete(ACCESS_CACHE_KEY)
        return {
            "registration_enabled": row.registration_enabled,
            "email_otp_login": row.email_otp_login,
        }

    @classmethod
    async def get_bot_settings(
        cls, db: AsyncSession, redis: aioredis.Redis
    ) -> Dict[str, Any]:
        cached = await redis.get(BOT_CACHE_KEY)
        if cached:
            try:
                return json.loads(cached)
            except Exception:
                pass

        row = await cls._get_row(db)
        data = {**DEFAULT_BOT_SETTINGS, **(row.bot_settings or {})}
        await redis.set(BOT_CACHE_KEY, json.dumps(data), ex=60)
        return data

    @classmethod
    async def update_bot_settings(
        cls,
        db: AsyncSession,
        redis: aioredis.Redis,
        admin_id,
        patch: Dict[str, Any],
    ) -> Dict[str, Any]:
        row = await cls._get_row(db)
        merged = {**DEFAULT_BOT_SETTINGS, **(row.bot_settings or {})}
        applied = {}
        for key, value in patch.items():
            if value is not None and key in DEFAULT_BOT_SETTINGS:
                merged[key] = value
                applied[key] = value

        row.bot_settings = merged
        db.add(
            AuditLog(
                admin_id=admin_id,
                action="platform.bot_settings_updated",
                resource_type="platform",
                resource_id=None,
                details=applied,
            )
        )
        await db.commit()
        await redis.delete(BOT_CACHE_KEY)
        return merged


    @staticmethod
    async def invalidate_caches(
        redis: aioredis.Redis, user_caches: bool = False
    ) -> None:
        await redis.delete(
            MODE_CACHE_KEY, FREE_LIMITS_CACHE_KEY, ACCESS_CACHE_KEY, BOT_CACHE_KEY
        )
        if not user_caches:
            return
        async for key in redis.scan_iter(match=SUB_CACHE_PATTERN, count=500):
            await redis.delete(key)


    @classmethod
    async def preflight(cls, db: AsyncSession) -> Dict[str, Any]:
        """Everything the admin needs to see before switching modes."""
        plans: List[Plan] = (
            await db.execute(select(Plan).order_by(Plan.price_inr.asc()))
        ).scalars().all()
        free_plan = next((p for p in plans if p.name == FREE), None)
        active_paid = [p for p in plans if p.is_active and not p.is_free]

        rows = (
            await db.execute(
                select(UserSubscription, Plan)
                .join(Plan, UserSubscription.plan_id == Plan.id)
                .where(UserSubscription.status == "active")
            )
        ).all()

        paid_user_ids = set()
        by_plan: Dict[str, int] = {}
        for sub, plan in rows:
            if plan.is_free:
                continue
            paid_user_ids.add(sub.user_id)
            by_plan[plan.name] = by_plan.get(plan.name, 0) + 1

        pending_payments = (
            await db.execute(
                select(PaymentOrder).where(PaymentOrder.status.in_(("created", "pending")))
            )
        ).scalars().all()

        mode_row = await cls._get_row(db)

        return {
            "platform_mode": mode_row.platform_mode,
            "mode_changed_at": (
                mode_row.mode_changed_at.isoformat()
                if mode_row.mode_changed_at
                else None
            ),
            "free_plan": _plan_summary(free_plan),
            "active_paid_plans": [
                {
                    "id": str(p.id),
                    "name": p.name,
                    "display_name": p.display_name,
                    "price_inr": p.price_inr,
                }
                for p in active_paid
            ],
            "active_paid_subscribers": len(paid_user_ids),
            "subscribers_by_plan": by_plan,
            "pending_payments": len(pending_payments),
        }


    @classmethod
    async def switch_to_free(
        cls,
        db: AsyncSession,
        redis: aioredis.Redis,
        admin_id,
        deactivate_plans: bool = False,
        cancel_pending_payments: bool = False,
    ) -> Dict[str, Any]:
        """
        Move the platform to free mode:
          - every active paid subscription is closed
          - affected users are moved onto the free plan
          - paid plans are deactivated (optional, otherwise the switch is refused)
          - pending payments are cancelled (optional, otherwise the switch is refused)
        """
        free_plan = await cls.get_free_plan(db)
        if not free_plan:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Free plan is not configured. Seed the free plan before switching.",
            )

        active_paid_plans = (
            await db.execute(
                select(Plan).where(Plan.is_active.is_(True), Plan.price_inr > 0)
            )
        ).scalars().all()
        if active_paid_plans and not deactivate_plans:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    f"{len(active_paid_plans)} paid plan(s) are still active. "
                    "Deactivate all paid plans before switching to Free mode."
                ),
            )

        pending_payments = (
            await db.execute(
                select(PaymentOrder).where(PaymentOrder.status.in_(("created", "pending")))
            )
        ).scalars().all()
        if pending_payments and not cancel_pending_payments:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    f"{len(pending_payments)} payment(s) are still pending. "
                    "Resolve or cancel them before switching to Free mode."
                ),
            )

        now = datetime.now(timezone.utc)

        # 1. Close every active paid subscription
        paid_subs = (
            await db.execute(
                select(UserSubscription)
                .join(Plan, UserSubscription.plan_id == Plan.id)
                .where(
                    UserSubscription.status == "active",
                    Plan.price_inr > 0,
                )
            )
        ).scalars().all()
        affected_user_ids = {sub.user_id for sub in paid_subs}
        for sub in paid_subs:
            sub.status = "expired"
            sub.updated_at = now

        await db.flush()

        # 2. Put those users on the free plan (unless they already have an active one)
        moved = 0
        if affected_user_ids:
            still_active = (
                await db.execute(
                    select(UserSubscription.user_id).where(
                        UserSubscription.user_id.in_(affected_user_ids),
                        UserSubscription.status == "active",
                    )
                )
            ).scalars().all()
            already_active = set(still_active)

            free_snapshot = free_plan.to_snapshot()
            free_expiry = get_ist_end_of_day_expiry(free_plan.validity_days)
            for user_id in affected_user_ids - already_active:
                db.add(
                    UserSubscription(
                        user_id=user_id,
                        plan_id=free_plan.id,
                        payment_id=None,
                        status="active",
                        started_at=now,
                        expires_at=free_expiry,
                        plan_snapshot=free_snapshot,
                        total_messages_used=0,
                        total_tokens_consumed=0,
                        total_conversations=0,
                    )
                )
                moved += 1

        # 3. Deactivate paid plans
        if active_paid_plans:
            await db.execute(
                update(Plan)
                .where(Plan.is_active.is_(True), Plan.price_inr > 0)
                .values(is_active=False, updated_at=now)
            )

        # 4. Cancel pending payments
        cancelled = 0
        if pending_payments:
            await db.execute(
                update(PaymentOrder)
                .where(PaymentOrder.status.in_(("created", "pending")))
                .values(
                    status="expired",
                    failure_reason="Platform switched to free mode.",
                    updated_at=now,
                )
            )
            cancelled = len(pending_payments)

        # 5. Flip the mode
        row = await cls._get_row(db)
        row.platform_mode = FREE
        row.mode_changed_at = now
        row.mode_changed_by = admin_id

        db.add(
            AuditLog(
                admin_id=admin_id,
                action="platform.mode_changed",
                resource_type="platform",
                resource_id=None,
                details={
                    "from": PAID,
                    "to": FREE,
                    "plans_deactivated": len(active_paid_plans),
                    "subscriptions_closed": len(paid_subs),
                    "users_moved_to_free": moved,
                    "pending_payments_cancelled": cancelled,
                },
            )
        )

        await db.commit()
        await cls.invalidate_caches(redis, user_caches=True)

        logger.warning(
            "platform.mode_changed paid->free by admin=%s plans=%s subs=%s moved=%s",
            admin_id,
            len(active_paid_plans),
            len(paid_subs),
            moved,
        )

        return {
            "platform_mode": FREE,
            "plans_deactivated": len(active_paid_plans),
            "subscriptions_closed": len(paid_subs),
            "users_moved_to_free": moved,
            "pending_payments_cancelled": cancelled,
        }

    @classmethod
    async def switch_to_paid(
        cls,
        db: AsyncSession,
        redis: aioredis.Redis,
        admin_id,
        reactivate_plans: bool = False,
    ) -> Dict[str, Any]:
        if reactivate_plans:
            await db.execute(
                update(Plan)
                .where(Plan.is_active.is_(False), Plan.price_inr > 0)
                .values(is_active=True, updated_at=datetime.now(timezone.utc))
            )
            await db.flush()

        active_paid_plans = (
            await db.execute(
                select(Plan).where(Plan.is_active.is_(True), Plan.price_inr > 0)
            )
        ).scalars().all()
        if not active_paid_plans:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "No paid plan is active. Activate at least one paid plan before "
                    "switching to Paid mode."
                ),
            )

        now = datetime.now(timezone.utc)
        row = await cls._get_row(db)
        previous = row.platform_mode
        row.platform_mode = PAID
        row.mode_changed_at = now
        row.mode_changed_by = admin_id

        db.add(
            AuditLog(
                admin_id=admin_id,
                action="platform.mode_changed",
                resource_type="platform",
                resource_id=None,
                details={
                    "from": previous,
                    "to": PAID,
                    "active_plans": [p.name for p in active_paid_plans],
                },
            )
        )

        await db.commit()
        await cls.invalidate_caches(redis, user_caches=True)

        logger.warning(
            "platform.mode_changed ->paid by admin=%s plans=%s",
            admin_id,
            [p.name for p in active_paid_plans],
        )

        return {
            "platform_mode": PAID,
            "active_plans": [p.name for p in active_paid_plans],
        }
