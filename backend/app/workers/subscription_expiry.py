"""
╔══════════════════════════════════════════════════════════════════╗
║  VIDHYA BOT — Subscription Expiry Worker                         ║
║  Celery Beat task:                                               ║
║    - Runs daily at UTC 00:05                                     ║
║    - Checks for active subscriptions past their expires_at date  ║
║    - Downgrades expired users to the Free plan                   ║
╚══════════════════════════════════════════════════════════════════╝
"""

import logging
import os
import uuid
from datetime import datetime, timezone, timedelta

import redis as redis_sync
from sqlalchemy import create_engine, select, update
from sqlalchemy.orm import Session

from app.models.subscription import UserSubscription
from app.models.plan import Plan
from app.models.user import User
from app.models.conversation import Conversation
from app.redis_client import RedisKeys
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)

DATABASE_URL_SYNC = os.getenv(
    "DATABASE_URL_SYNC",
    "postgresql://vidhya:CHANGE_ME@postgres:5432/vidhya_db"
)
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")


def get_redis():
    return redis_sync.from_url(REDIS_URL, decode_responses=True)


def get_engine():
    return create_engine(DATABASE_URL_SYNC, pool_pre_ping=True)


@celery_app.task(
    name="vidhya.expire_subscriptions",
    queue="quota",
    acks_late=True,
)
def expire_subscriptions():
    """
    Finds subscriptions where `expires_at` is in the past and status is 'active'.
    Downgrades them to 'free' and resets Redis cache.
    """
    r = get_redis()
    engine = get_engine()
    ist_tz = timezone(timedelta(hours=5, minutes=30))
    now_ist = datetime.now(ist_tz)
    
    with Session(engine) as db:
        # 1. Find the free plan
        free_plan = db.execute(select(Plan).where(Plan.name == "free")).scalar_one_or_none()
        if not free_plan:
            logger.error("Free plan not found in DB! Cannot downgrade users.")
            return {"status": "error", "message": "Free plan not found"}

        # 2. Find expired active subscriptions with user info
        expired_subs = db.execute(
            select(UserSubscription, User)
            .join(User, UserSubscription.user_id == User.id)
            .where(UserSubscription.status == "active")
            .where(UserSubscription.expires_at < now_ist)
            .where(UserSubscription.plan_id != free_plan.id)  # Don't expire lifetime free plans
        ).all()
        
        if not expired_subs:
            logger.info("expire_subscriptions: No expired subscriptions found.")
            return {"status": "complete", "downgraded_count": 0}
            
        downgraded_users = []
        downgraded_count = 0
        
        for sub, user in expired_subs:
            try:
                old_plan_name = sub.plan_snapshot.get("plan_name", "unknown")
                
                # Mark as expired
                sub.status = "expired"
                sub.updated_at = now_ist
                
                # Create a new free subscription
                new_sub = UserSubscription(
                    user_id=sub.user_id,
                    plan_id=free_plan.id,
                    payment_id=None,
                    status="active",
                    started_at=now_ist,
                    expires_at=now_ist + timedelta(days=free_plan.validity_days),
                    plan_snapshot=free_plan.to_snapshot(),
                    total_messages_used=0,
                    total_tokens_consumed=0,
                    total_conversations=0
                )
                db.add(new_sub)
                
                # Close all active conversations to enforce Free tier limit
                db.execute(
                    update(Conversation)
                    .where(Conversation.user_id == sub.user_id)
                    .where(Conversation.status == "active")
                    .values(status="timeout", closed_at=now_ist)
                )
                
                # Clear User Subscription Cache & Quota so limits reload dynamically
                cache_key = RedisKeys.subscription_cache(str(sub.user_id))
                r.delete(cache_key)
                
                downgraded_count += 1
                downgraded_users.append({
                    "user_id": str(user.id),
                    "username": user.telegram_username or "N/A",
                    "first_name": user.first_name,
                    "telegram_id": user.telegram_id,
                    "from_plan": old_plan_name,
                })
                logger.info(
                    f"[DOWNGRADE] user_id={user.id} | "
                    f"name={user.first_name} (@{user.telegram_username}) | "
                    f"telegram_id={user.telegram_id} | "
                    f"{old_plan_name} → free"
                )
                
            except Exception as e:
                logger.error(f"Failed to downgrade user {sub.user_id}: {e}")
                
        # Commit all downgrades
        db.commit()

    logger.info(
        f"expire_subscriptions: downgraded {downgraded_count} users to free plan. "
        f"Users: {[u['first_name'] + '(@' + u['username'] + ') id=' + str(u['telegram_id']) for u in downgraded_users]}"
    )
    
    return {
        "status": "complete",
        "downgraded_count": downgraded_count,
        "downgraded_users": downgraded_users,
        "run_at": now_ist.isoformat(),
    }
