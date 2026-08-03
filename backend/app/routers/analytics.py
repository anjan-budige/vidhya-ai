"""
╔══════════════════════════════════════════════════════════════════╗
║  VIDHYA BOT — Analytics Router                                   ║
║  Provides: Real-time telemetry dashboard statistics for admin    ║
║  portals.                                                        ║
╚══════════════════════════════════════════════════════════════════╝
"""

import time
from datetime import date, datetime, timezone
from typing import Dict, Any

from fastapi import APIRouter, Depends, status
import httpx
from sqlalchemy import select, func, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import engine
from app.redis_client import redis_client
from app.config import get_settings
from app.workers.celery_app import celery_app
from app.dependencies import get_db, get_current_admin, require_admin_or_above
from app.models.user import User
from app.models.conversation import Conversation
from app.models.usage_tracking import UsageTracking
from app.models.payment import Payment
from app.models.subscription import UserSubscription
from app.models.document import Document
from app.schemas.analytics import DashboardStats
from app.schemas.auth import CurrentAdmin

router = APIRouter(prefix="/analytics", tags=["Analytics"])


@router.get("/dashboard", response_model=DashboardStats, status_code=status.HTTP_200_OK)
async def get_admin_dashboard_stats(
    current_admin: CurrentAdmin = Depends(require_admin_or_above),
    db: AsyncSession = Depends(get_db)
):
    """
    Generate live telemetry statistics for admin portals (Admin only).
    Performs fast real-time aggregates across PostgreSQL tables.
    """
    today = date.today()
    first_of_month = today.replace(day=1)
    
    # 1. User count aggregates
    user_cnt_stmt = select(func.count(User.id))
    total_users = (await db.execute(user_cnt_stmt)).scalar() or 0
    
    active_usr_stmt = select(func.count(User.id)).where(User.last_login_at >= datetime(today.year, today.month, today.day, tzinfo=timezone.utc))
    active_users_today = (await db.execute(active_usr_stmt)).scalar() or 0
    
    # 2. Conversation aggregates
    conv_cnt_stmt = select(func.count(Conversation.id))
    total_conversations = (await db.execute(conv_cnt_stmt)).scalar() or 0
    
    active_conv_stmt = select(func.count(Conversation.id)).where(Conversation.status == "active")
    active_conversations = (await db.execute(active_conv_stmt)).scalar() or 0
    
    # 3. Message & Token telemetry today (Usage records)
    msg_sum_stmt = select(func.sum(UsageTracking.messages_used)).where(UsageTracking.period_type == "daily", UsageTracking.period_date == today)
    total_messages_today = (await db.execute(msg_sum_stmt)).scalar() or 0
    
    token_sum_stmt = select(func.sum(UsageTracking.tokens_input + UsageTracking.tokens_output)).where(UsageTracking.period_type == "daily", UsageTracking.period_date == today)
    total_tokens_today = (await db.execute(token_sum_stmt)).scalar() or 0
    
    # 4. Revenue statistics (Amount stored in Paise)
    rev_sum_stmt = select(func.sum(Payment.amount_inr)).where(Payment.status == "success")
    total_revenue_paise = (await db.execute(rev_sum_stmt)).scalar() or 0
    total_revenue = float(total_revenue_paise / 100)
    
    month_rev_stmt = select(func.sum(Payment.amount_inr)).where(Payment.status == "success", Payment.completed_at >= datetime(today.year, today.month, 1, tzinfo=timezone.utc))
    revenue_this_month_paise = (await db.execute(month_rev_stmt)).scalar() or 0
    revenue_this_month = float(revenue_this_month_paise / 100)
    
    # 5. Subscription count aggregates
    active_sub_stmt = select(func.count(UserSubscription.id)).where(UserSubscription.status == "active")
    active_subscriptions = (await db.execute(active_sub_stmt)).scalar() or 0
    
    # 6. Document density
    doc_cnt_stmt = select(func.count(Document.id))
    total_documents = (await db.execute(doc_cnt_stmt)).scalar() or 0
    
    return DashboardStats(
        total_users=total_users,
        active_users_today=active_users_today,
        total_conversations=total_conversations,
        active_conversations=active_conversations,
        total_messages_today=total_messages_today,
        total_tokens_today=total_tokens_today,
        total_revenue=total_revenue,
        revenue_this_month=revenue_this_month,
        active_subscriptions=active_subscriptions,
        total_documents=total_documents
    )


@router.get("/system-health", status_code=status.HTTP_200_OK)
async def get_admin_system_health(
    current_admin: CurrentAdmin = Depends(require_admin_or_above)
):
    """
    Detailed health check for Admin Dashboard — verifies connectivity to all infra.
    Returns individual status, latency, memory, table count, and models.
    """
    import time
    from app.main import startup_time
    
    settings = get_settings()
    results = {
        "status": "healthy",
        "service": settings.APP_NAME,
        "version": "3.0.0",
        "environment": settings.ENV,
        "uptime_seconds": round(time.time() - startup_time, 2) if startup_time else 0,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "services": {},
    }

    all_healthy = True

    # ── PostgreSQL ────────────────────────────────────────────────
    try:
        start = time.time()
        async with engine.begin() as conn:
            result = await conn.execute(text("SELECT 1"))
            result.scalar()
        latency_ms = round((time.time() - start) * 1000, 1)
        results["services"]["postgres"] = {
            "status": "connected",
            "latency_ms": latency_ms,
        }
    except Exception as e:
        results["services"]["postgres"] = {
            "status": "disconnected",
            "error": str(e),
        }
        all_healthy = False

    try:
        async with engine.begin() as conn:
            result = await conn.execute(
                text("SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'public' AND table_type = 'BASE TABLE'")
            )
            table_count = result.scalar()
        results["services"]["postgres"]["tables"] = table_count
    except Exception:
        pass

    # ── Redis ─────────────────────────────────────────────────────
    try:
        start = time.time()
        pong = await redis_client.ping()
        latency_ms = round((time.time() - start) * 1000, 1)
        info = await redis_client.info("memory")
        results["services"]["redis"] = {
            "status": "connected" if pong else "error",
            "latency_ms": latency_ms,
            "used_memory": info.get("used_memory_human", "unknown"),
        }
    except Exception as e:
        results["services"]["redis"] = {
            "status": "disconnected",
            "error": str(e),
        }
        all_healthy = False

    # ── Mistral API ───────────────────────────────────────────────
    try:
        start = time.time()
        async with httpx.AsyncClient(timeout=3.0) as client:
            response = await client.get(
                "https://api.mistral.ai/v1/models",
                headers={"Authorization": f"Bearer {settings.MISTRAL_API_KEY}"}
            )
            latency_ms = round((time.time() - start) * 1000, 1)

            if response.status_code == 200:
                data = response.json()
                models = [m["id"] for m in data.get("data", [])]
                results["services"]["mistral"] = {
                    "status": "connected",
                    "latency_ms": latency_ms,
                    "models_loaded": models[:5], # Only list top 5 to save space
                    "model_count": len(models),
                }
            else:
                results["services"]["mistral"] = {
                    "status": "error",
                    "http_status": response.status_code,
                }
                all_healthy = False
    except Exception as e:
        results["services"]["mistral"] = {
            "status": "disconnected",
            "error": str(e),
        }
        all_healthy = False

    # ── Celery Workers ────────────────────────────────────────────
    try:
        start = time.time()
        i = celery_app.control.inspect(timeout=1.0)
        pings = i.ping()
        latency_ms = round((time.time() - start) * 1000, 1)

        if pings:
            worker_count = len(pings)
            results["services"]["celery"] = {
                "status": "connected",
                "latency_ms": latency_ms,
                "workers_online": worker_count,
                "nodes": list(pings.keys())
            }
        else:
            results["services"]["celery"] = {
                "status": "error",
                "message": "No active workers found",
                "latency_ms": latency_ms
            }
            all_healthy = False
    except Exception as e:
        results["services"]["celery"] = {
            "status": "disconnected",
            "error": str(e)
        }
        all_healthy = False

    results["status"] = "healthy" if all_healthy else "degraded"
    return results
