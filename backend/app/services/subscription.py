"""
Vidhya AI — Subscription service.

Free-plan provisioning, admin assignment, and paid-plan activation after a
verified payment. PhonePe-specific code moved to app.services.payments.
"""

import json
import logging
import uuid
from datetime import datetime, timedelta, timezone

import redis.asyncio as aioredis
from fastapi import HTTPException, status
from sqlalchemy import select, update
from sqlalchemy.orm import joinedload
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.plan import Plan
from app.models.subscription import UserSubscription
from app.redis_client import RedisKeys

settings = None  # retained for backwards import compatibility
logger = logging.getLogger("vidhya.subscription")


def get_ist_end_of_day_expiry(days_valid: int) -> datetime:
    ist_tz = timezone(timedelta(hours=5, minutes=30))
    now_ist = datetime.now(ist_tz)
    target = now_ist + timedelta(days=days_valid)
    return target.replace(hour=23, minute=59, second=59, microsecond=999999)


class SubscriptionService:
    """Plans, provisioning, and plan activation."""

    @staticmethod
    async def _deactivate_active(user_id: uuid.UUID, db: AsyncSession) -> None:
        await db.execute(
            update(UserSubscription)
            .where(
                UserSubscription.user_id == user_id,
                UserSubscription.status == "active",
            )
            .values(status="expired", updated_at=datetime.now(timezone.utc))
        )

    @staticmethod
    async def activate_free_plan(
        user_id: uuid.UUID,
        db: AsyncSession,
        redis: aioredis.Redis,
    ) -> UserSubscription:
        result = await db.execute(select(Plan).where(Plan.name == "free"))
        free_plan = result.scalar_one_or_none()

        if not free_plan:
            free_plan = Plan(
                name="free",
                display_name="Free Tier",
                description="Default free plan",
                price_inr=0,
                validity_days=3650,
                messages_per_day=5,
                messages_per_month=50,
                max_sessions=5,
                max_context_tokens=2000,
                max_response_tokens=512,
                memory_retention_days=7,
                summary_frequency=10,
            )
            db.add(free_plan)
            await db.flush()

        await SubscriptionService._deactivate_active(user_id, db)

        subscription = UserSubscription(
            user_id=user_id,
            plan_id=free_plan.id,
            payment_id=None,
            status="active",
            started_at=datetime.now(timezone.utc),
            expires_at=get_ist_end_of_day_expiry(free_plan.validity_days),
            plan_snapshot=free_plan.to_snapshot(),
            total_messages_used=0,
            total_tokens_consumed=0,
            total_conversations=0,
        )
        db.add(subscription)
        await db.flush()

        await redis.set(
            RedisKeys.subscription_cache(str(user_id)),
            json.dumps(subscription.plan_limits),
            ex=3600,
        )
        return subscription

    @classmethod
    async def admin_assign_plan(
        cls,
        user_id: uuid.UUID,
        plan_id: uuid.UUID,
        db: AsyncSession,
        redis: aioredis.Redis,
    ) -> UserSubscription:
        result = await db.execute(select(Plan).where(Plan.id == plan_id))
        plan = result.scalar_one_or_none()

        if not plan or not plan.is_active:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Plan not found or deactivated.",
            )

        await cls._deactivate_active(user_id, db)

        subscription = UserSubscription(
            user_id=user_id,
            plan_id=plan.id,
            payment_id=None,
            status="active",
            started_at=datetime.now(timezone.utc),
            expires_at=get_ist_end_of_day_expiry(plan.validity_days),
            plan_snapshot=plan.to_snapshot(),
            total_messages_used=0,
            total_tokens_consumed=0,
            total_conversations=0,
        )
        db.add(subscription)
        await db.flush()

        await redis.delete(RedisKeys.subscription_cache(str(user_id)))
        usage_cache_key = RedisKeys.quota_daily(
            str(user_id), datetime.now(timezone.utc).strftime("%Y-%m-%d")
        )
        await redis.delete(usage_cache_key)
        return subscription

    @classmethod
    async def activate_paid_plan(
        cls,
        user_id: uuid.UUID,
        plan: Plan,
        payment_id: uuid.UUID,
        db: AsyncSession,
        redis: aioredis.Redis,
    ) -> UserSubscription | None:
        """Grant a paid plan after a verified payment.

        Returns None when a more expensive plan is already active, so a delayed
        webhook can never downgrade the user.
        """
        active_sub = (
            await db.execute(
                select(UserSubscription)
                .options(joinedload(UserSubscription.plan))
                .where(
                    UserSubscription.user_id == user_id,
                    UserSubscription.status == "active",
                )
            )
        ).scalar_one_or_none()

        if active_sub and not active_sub.plan.is_free:
            if active_sub.plan.price_inr > plan.price_inr:
                logger.warning(
                    "Prevented downgrade: user %s has %s, payment was for %s",
                    user_id,
                    active_sub.plan.name,
                    plan.name,
                )
                return None

        await cls._deactivate_active(user_id, db)

        subscription = UserSubscription(
            user_id=user_id,
            plan_id=plan.id,
            payment_id=payment_id,
            status="active",
            started_at=datetime.now(timezone.utc),
            expires_at=get_ist_end_of_day_expiry(plan.validity_days),
            plan_snapshot=plan.to_snapshot(),
            total_messages_used=0,
            total_tokens_consumed=0,
            total_conversations=0,
        )
        db.add(subscription)
        await db.flush()

        await redis.set(
            RedisKeys.subscription_cache(str(user_id)),
            json.dumps(subscription.plan_limits),
            ex=3600,
        )
        return subscription
