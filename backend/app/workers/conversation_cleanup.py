"""
╔══════════════════════════════════════════════════════════════════╗
║  VIDHYA BOT — Conversation Cleanup Worker (Phase 5)              ║
║  Celery Beat task runs every 30 minutes:                         ║
║    1. Times out conversations idle beyond their plan limit       ║
║    2. Archives conversations where memory_retention_days expired ║
║    3. Cleans subscription cache keys for affected users          ║
╚══════════════════════════════════════════════════════════════════╝
"""

import logging
import os
from datetime import datetime, timezone, timedelta

import redis as redis_sync
from sqlalchemy import create_engine, select, update
from sqlalchemy.orm import Session

from app.models.conversation import Conversation
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
    name="vidhya.cleanup_conversations",
    queue="conversations",
    acks_late=True,
)
def cleanup_conversations():
    """
    Periodic sweep of all active conversations:
    - Times out conversations idle beyond their per-plan timeout window.
    - Archives conversations whose messages are outside memory_retention_days.
    """
    now = datetime.now(timezone.utc)
    engine = get_engine()
    r = get_redis()

    timed_out = 0
    archived = 0
    affected_user_ids = set()

    # Grace window: never touch conversations active in the last 5 min
    # (protects users who are actively reading/typing between sweep cycles)
    GRACE_MINUTES = 5

    with Session(engine) as db:
        # ── 1. Load all active conversations ──────────────────────────
        active_convs = db.execute(
            select(Conversation).where(Conversation.status == "active")
        ).scalars().all()

        for conv in active_convs:
            close_reason = None

            last_active = conv.last_activity_at.replace(tzinfo=timezone.utc)
            idle_minutes = (now - last_active).total_seconds() / 60

            # Skip if user was active within the grace window
            if idle_minutes < GRACE_MINUTES:
                continue

            # ── Timeout check ─────────────────────────────────────────
            if idle_minutes >= conv.conversation_timeout_min:
                close_reason = "timeout"
                timed_out += 1

            # ── Memory retention check ────────────────────────────────
            elif conv.memory_retention_days > 0:
                age_days = (now - conv.started_at.replace(tzinfo=timezone.utc)).days
                if age_days >= conv.memory_retention_days:
                    close_reason = "archived"
                    archived += 1

            if close_reason:
                conv.status = close_reason if close_reason != "archived" else "archived"
                conv.closed_at = now
                conv.auto_close_reason = close_reason
                affected_user_ids.add(str(conv.user_id))

        db.commit()

    # ── 2. Invalidate subscription cache for affected users ───────────
    from app.redis_client import RedisKeys
    for uid in affected_user_ids:
        cache_key = RedisKeys.subscription_cache(uid)
        r.delete(cache_key)

    logger.info(
        f"cleanup_conversations: timed_out={timed_out}, archived={archived}, "
        f"users_affected={len(affected_user_ids)}"
    )
    return {
        "status": "cleanup_complete",
        "timed_out": timed_out,
        "archived": archived,
        "users_affected": len(affected_user_ids),
        "run_at": now.isoformat(),
    }
