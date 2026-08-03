"""
╔══════════════════════════════════════════════════════════════════╗
║  VIDHYA BOT — Quota Reset Worker (Phase 5)                       ║
║  Celery Beat tasks:                                              ║
║    1. Daily quota reset  — runs at UTC midnight every day        ║
║    2. Monthly quota reset — runs at UTC midnight on 1st of month ║
║    Both tasks clear Redis quota keys AND sync DB usage_tracking  ║
╚══════════════════════════════════════════════════════════════════╝
"""

import logging
import os
from datetime import date, datetime, timezone, timedelta

import redis as redis_sync
from sqlalchemy import create_engine, select, delete
from sqlalchemy.orm import Session

from app.models.usage_tracking import UsageTracking
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
    name="vidhya.reset_daily_quotas",
    queue="quota",
    acks_late=True,
)
def reset_daily_quotas():
    """
    Runs at UTC midnight daily.
    - Deletes all Redis daily quota keys for ALL users.
    - Clears daily UsageTracking rows older than 30 days from Postgres.
    """
    r = get_redis()
    engine = get_engine()

    # 1. Flush all daily quota Redis keys
    pattern = "quota:daily:*"
    cursor = 0
    deleted_redis = 0
    while True:
        cursor, keys = r.scan(cursor=cursor, match=pattern, count=500)
        if keys:
            r.delete(*keys)
            deleted_redis += len(keys)
        if cursor == 0:
            break

    # 2. Purge stale daily usage rows (older than 30 days) from DB
    cutoff = date.today() - timedelta(days=30)
    with Session(engine) as db:
        result = db.execute(
            delete(UsageTracking)
            .where(UsageTracking.period_type == "daily")
            .where(UsageTracking.period_date < cutoff)
        )
        db.commit()
        deleted_db = result.rowcount

    logger.info(
        f"reset_daily_quotas: cleared {deleted_redis} Redis keys, "
        f"purged {deleted_db} stale DB rows"
    )
    return {
        "status": "daily_reset_complete",
        "redis_keys_cleared": deleted_redis,
        "db_rows_purged": deleted_db,
        "reset_at": datetime.now(timezone.utc).isoformat(),
    }


@celery_app.task(
    name="vidhya.reset_monthly_quotas",
    queue="quota",
    acks_late=True,
)
def reset_monthly_quotas():
    """
    Runs at UTC midnight on the 1st of every month.
    - Deletes all Redis monthly quota keys.
    - Clears monthly UsageTracking rows older than 12 months from Postgres.
    """
    r = get_redis()
    engine = get_engine()

    # 1. Flush all monthly quota Redis keys
    pattern = "quota:monthly:*"
    cursor = 0
    deleted_redis = 0
    while True:
        cursor, keys = r.scan(cursor=cursor, match=pattern, count=500)
        if keys:
            r.delete(*keys)
            deleted_redis += len(keys)
        if cursor == 0:
            break

    # 2. Purge stale monthly usage rows (older than 12 months)
    cutoff = date.today().replace(day=1) - timedelta(days=365)
    with Session(engine) as db:
        result = db.execute(
            delete(UsageTracking)
            .where(UsageTracking.period_type == "monthly")
            .where(UsageTracking.period_date < cutoff)
        )
        db.commit()
        deleted_db = result.rowcount

    logger.info(
        f"reset_monthly_quotas: cleared {deleted_redis} Redis keys, "
        f"purged {deleted_db} stale DB rows"
    )
    return {
        "status": "monthly_reset_complete",
        "redis_keys_cleared": deleted_redis,
        "db_rows_purged": deleted_db,
        "reset_at": datetime.now(timezone.utc).isoformat(),
    }
