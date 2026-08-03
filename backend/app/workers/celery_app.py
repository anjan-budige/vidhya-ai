"""
╔══════════════════════════════════════════════════════════════════╗
║  VIDHYA BOT — Celery Application                                 ║
║  Task queues: pdf | quota | conversations | default              ║
║  Beat schedule: daily quota reset, monthly quota reset,          ║
║                 conversation cleanup sweep (every 30 min)        ║
╚══════════════════════════════════════════════════════════════════╝
"""

import os

from celery import Celery
from celery.schedules import crontab

CELERY_BROKER_URL    = os.getenv("CELERY_BROKER_URL",    "redis://redis:6379/1")
CELERY_RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", "redis://redis:6379/2")

celery_app = Celery(
    "vidhya",
    broker=CELERY_BROKER_URL,
    backend=CELERY_RESULT_BACKEND,
    include=[
        "app.workers.pdf_ingest",
        "app.workers.quota_reset",
        "app.workers.conversation_cleanup",
        "app.workers.conversation_summarizer",
        "app.workers.subscription_expiry",
    ],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Asia/Kolkata",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_default_queue="default",
    broker_connection_retry_on_startup=True,  # Suppress Celery 6.0 deprecation warning
    task_queues={
        "pdf":           {"exchange": "pdf",           "routing_key": "pdf"},
        "analytics":     {"exchange": "analytics",     "routing_key": "analytics"},
        "quota":         {"exchange": "quota",         "routing_key": "quota"},
        "conversations": {"exchange": "conversations", "routing_key": "conversations"},
    },
    # ── Beat Periodic Schedule ────────────────────────────────────────────────
    beat_schedule={
        # Daily quota reset — runs at 00:00 UTC every day
        "reset-daily-quotas": {
            "task": "vidhya.reset_daily_quotas",
            "schedule": crontab(hour=0, minute=0),
            "options": {"queue": "quota"},
        },
        # Monthly quota reset — runs at 00:00 UTC on the 1st of every month
        "reset-monthly-quotas": {
            "task": "vidhya.reset_monthly_quotas",
            "schedule": crontab(hour=0, minute=0, day_of_month=1),
            "options": {"queue": "quota"},
        },
        # Expire plans past validity — runs at 00:05 UTC every day
        "expire-subscriptions": {
            "task": "vidhya.expire_subscriptions",
            "schedule": crontab(hour=0, minute=5),
            "options": {"queue": "quota"},
        },
        # Conversation cleanup sweep — every 30 minutes
        "cleanup-conversations": {
            "task": "vidhya.cleanup_conversations",
            "schedule": crontab(minute="*/30"),
            "options": {"queue": "conversations"},
        },
    },
)

@celery_app.task(name="vidhya.health_check")
def celery_health_check():
    """Simple task to verify Celery worker is alive."""
    return {"status": "celery_healthy", "worker": "vidhya"}
