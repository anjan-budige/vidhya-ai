import json
import uuid
from datetime import date, datetime, timezone, timedelta
from typing import Optional, Tuple, Dict, Any

import redis.asyncio as aioredis
from fastapi import HTTPException, status
from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.subscription import UserSubscription
from app.models.usage_tracking import UsageTracking
from app.models.plan import Plan
from app.redis_client import RedisKeys

settings = get_settings()


class QuotaService:
    """Enforces daily and monthly limits on messages and document ingestion."""

    @classmethod
    async def get_active_subscription_limits(
        cls,
        user_id: uuid.UUID,
        db: AsyncSession,
        redis: aioredis.Redis
    ) -> Dict[str, Any]:
        """
        Retrieve active subscription limits for a user.
        Checks Redis cache first; falls back to DB query and caches results.
        Automatically provisions the default "free" plan if none is active.
        """
        from app.services.platform import FREE, PlatformConfigService

        # Free mode: the free plan row IS the platform's limits. Bypass any
        # per-user snapshot/cache so a paid plan can never leak through.
        mode = await PlatformConfigService.get_mode(db, redis)
        if mode == FREE:
            return await PlatformConfigService.get_free_limits(db, redis)

        cache_key = RedisKeys.subscription_cache(str(user_id))
        cached_limits = await redis.get(cache_key)
        
        if cached_limits:
            try:
                return json.loads(cached_limits)
            except Exception:
                pass  # Parse error, fallback to DB
                
        result = await db.execute(
            select(UserSubscription)
            .where(UserSubscription.user_id == user_id)
            .where(UserSubscription.status == "active")
        )
        subscription = result.scalar_one_or_none()
        
        if not subscription:
            # Auto-provision "Free" plan
            from app.services.subscription import SubscriptionService
            subscription = await SubscriptionService.activate_free_plan(user_id, db, redis)
            
        limits = subscription.plan_limits
        # Cache for 1 hour to ensure updates are periodically propagated
        await redis.set(cache_key, json.dumps(limits), ex=3600)
        return limits

    @classmethod
    async def check_quota(
        cls,
        user_id: uuid.UUID,
        quota_type: str,  # 'messages' | 'documents'
        increment: int,
        db: AsyncSession,
        redis: aioredis.Redis
    ) -> Tuple[bool, Dict[str, Any]]:
        """
        Check if user has remaining quota before performing an action.
        Returns a tuple of (is_allowed, details).
        Does NOT increment counters.
        """
        limits = await cls.get_active_subscription_limits(user_id, db, redis)

        ist_tz = timezone(timedelta(hours=5, minutes=30))
        today = datetime.now(ist_tz).date()
        date_str = today.strftime("%Y-%m-%d")
        month_str = today.strftime("%Y-%m")
        
        # 1. Evaluate limits from subscription snapshot
        if quota_type == "messages":
            daily_limit = limits.get("messages_per_day", 5)
            monthly_limit = limits.get("messages_per_month", 50)
        elif quota_type == "documents":
            daily_limit = -1  # Documents usually only have monthly limits
            monthly_limit = limits.get("features", {}).get("documents_per_month", 5)
            # Fallback if not inside nested features block
            if not isinstance(monthly_limit, int):
                monthly_limit = limits.get("documents_per_month", 5)
        else:
            raise ValueError(f"Invalid quota type: {quota_type}")
            
        # 2. Daily counter — always read so usage is accurate even when unlimited.
        daily_key = RedisKeys.quota_daily(str(user_id), date_str)
        daily_val = await redis.get(daily_key)

        if daily_val is None:
            db_result = await db.execute(
                select(UsageTracking)
                .where(UsageTracking.user_id == user_id)
                .where(UsageTracking.period_type == "daily")
                .where(UsageTracking.period_date == today)
            )
            db_record = db_result.scalar_one_or_none()
            daily_used = db_record.messages_used if db_record else 0
            await redis.set(daily_key, str(daily_used), ex=86400)
        else:
            daily_used = int(daily_val)

        if daily_limit != -1:
            if daily_used + increment > daily_limit:
                return False, {
                    "limit_type": "daily",
                    "quota_type": quota_type,
                    "used": daily_used,
                    "limit": daily_limit,
                    "remaining": max(0, daily_limit - daily_used)
                }

        # 3. Monthly counter — always read for accurate reporting.
        monthly_used = 0
        monthly_key = RedisKeys.quota_monthly(str(user_id), month_str)
        monthly_val = await redis.get(monthly_key)

        if monthly_val is None:
                # Fallback to DB (First day of month)
                first_of_month = today.replace(day=1)
                db_result = await db.execute(
                    select(UsageTracking)
                    .where(UsageTracking.user_id == user_id)
                    .where(UsageTracking.period_type == "monthly")
                    .where(UsageTracking.period_date == first_of_month)
                )
                db_record = db_result.scalar_one_or_none()
                monthly_used = (
                    db_record.messages_used if quota_type == "messages"
                    else db_record.conversations_created  # Use conversations/docs field or standard message
                ) if db_record else 0
                
                # For document ingestion, count total documents uploaded this month
                if quota_type == "documents":
                    # Let's count in DB if no record exists
                    from app.models.document import Document
                    doc_result = await db.execute(
                        select(Document)
                        .where(Document.user_id == user_id)
                        .where(Document.created_at >= datetime(today.year, today.month, 1, tzinfo=timezone.utc))
                    )
                    monthly_used = len(doc_result.scalars().all())
                    
                await redis.set(monthly_key, str(monthly_used), ex=30 * 86400)
        else:
            monthly_used = int(monthly_val)

        if monthly_limit != -1:
            if monthly_used + increment > monthly_limit:
                return False, {
                    "limit_type": "monthly",
                    "quota_type": quota_type,
                    "used": monthly_used,
                    "limit": monthly_limit,
                    "remaining": max(0, monthly_limit - monthly_used)
                }
                
        return True, {
            "allowed": True,
            "daily_used": daily_used,
            "monthly_used": monthly_used,
            "daily_remaining": max(0, daily_limit - daily_used) if daily_limit != -1 else -1,
            "monthly_remaining": max(0, monthly_limit - monthly_used) if monthly_limit != -1 else -1
        }

    @classmethod
    async def increment_quota(
        cls,
        user_id: uuid.UUID,
        quota_type: str,
        increment: int,
        db: AsyncSession,
        redis: aioredis.Redis,
        bypass_db: bool = False,
        tokens_input: int = 0,
        tokens_output: int = 0
    ) -> Dict[str, Any]:
        """
        Increment the user's daily and monthly usage counters.
        Updates Redis hot-counters immediately, and spawns/triggers DB write.
        """
        ist_tz = timezone(timedelta(hours=5, minutes=30))
        today = datetime.now(ist_tz).date()
        date_str = today.strftime("%Y-%m-%d")
        month_str = today.strftime("%Y-%m")
        
        # 1/2. Always track usage so the counters stay correct when a limit
        # is later changed from unlimited to a finite value.
        daily_key = RedisKeys.quota_daily(str(user_id), date_str)
        daily_used = await redis.incrby(daily_key, increment)
        if daily_used == increment:
            await redis.expire(daily_key, 86400)

        monthly_key = RedisKeys.quota_monthly(str(user_id), month_str)
        monthly_used = await redis.incrby(monthly_key, increment)
        if monthly_used == increment:
            await redis.expire(monthly_key, 30 * 86400)
            
        # 3. DB Sync
        if not bypass_db:
            # For now we write to DB directly using a highly efficient UPSERT statement
            await cls.sync_quota_to_db(user_id, quota_type, increment, db, tokens_input=tokens_input, tokens_output=tokens_output)
            
        return {
            "quota_type": quota_type,
            "daily_used": daily_used,
            "monthly_used": monthly_used
        }

    @staticmethod
    async def sync_quota_to_db(
        user_id: uuid.UUID,
        quota_type: str,
        increment: int,
        db: AsyncSession,
        tokens_input: int = 0,
        tokens_output: int = 0
    ) -> None:
        """
        Persist quota increments into PostgreSQL UsageTracking.
        Executes efficient PostgreSQL UPSERT (INSERT ... ON CONFLICT).
        """
        ist_tz = timezone(timedelta(hours=5, minutes=30))
        today = datetime.now(ist_tz).date()
        first_of_month = today.replace(day=1)
        
        # We need to update BOTH daily and monthly records in the DB
        periods = [
            ("daily", today),
            ("monthly", first_of_month)
        ]
        
        sub_result = await db.execute(
            select(UserSubscription)
            .where(UserSubscription.user_id == user_id)
            .where(UserSubscription.status == "active")
        )
        sub = sub_result.scalar_one_or_none()
        sub_id = sub.id if sub else None
        
        for period_type, period_date in periods:
            insert_vals = {
                "id": uuid.uuid4(),
                "user_id": user_id,
                "subscription_id": sub_id,
                "period_type": period_type,
                "period_date": period_date,
                "messages_used": increment if quota_type == "messages" else 0,
                "conversations_created": increment if quota_type == "documents" else 0,
                "tokens_input": tokens_input,
                "tokens_output": tokens_output,
                "created_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc)
            }
            
            # Execute PG vector-safe UPSERT
            stmt = insert(UsageTracking).values(insert_vals)
            
            # On conflict: update counters
            update_dict = {
                "updated_at": datetime.now(timezone.utc),
                "tokens_input": UsageTracking.tokens_input + tokens_input,
                "tokens_output": UsageTracking.tokens_output + tokens_output
            }
            if quota_type == "messages":
                update_dict["messages_used"] = UsageTracking.messages_used + increment
            elif quota_type == "documents":
                update_dict["conversations_created"] = UsageTracking.conversations_created + increment
                
            stmt = stmt.on_conflict_do_update(
                index_elements=["user_id", "period_type", "period_date"],
                set_=update_dict
            )
            
            await db.execute(stmt)
            
        await db.flush()
