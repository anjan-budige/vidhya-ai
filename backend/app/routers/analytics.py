import time
from datetime import date, datetime, timedelta, timezone
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
from app.models.message import Message
from app.models.plan import Plan
from app.models.usage_tracking import UsageTracking
from app.models.payment import PaymentOrder
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
    
    # 3. Message & Token telemetry today (Usage records)
    msg_sum_stmt = select(func.sum(UsageTracking.messages_used)).where(UsageTracking.period_type == "daily", UsageTracking.period_date == today)
    total_messages_today = (await db.execute(msg_sum_stmt)).scalar() or 0
    
    token_sum_stmt = select(func.sum(UsageTracking.tokens_input + UsageTracking.tokens_output)).where(UsageTracking.period_type == "daily", UsageTracking.period_date == today)
    total_tokens_today = (await db.execute(token_sum_stmt)).scalar() or 0
    
    # 4. Revenue statistics (Amount stored in Paise)
    rev_sum_stmt = select(func.sum(PaymentOrder.amount_paise)).where(PaymentOrder.status == "paid")
    total_revenue_paise = (await db.execute(rev_sum_stmt)).scalar() or 0
    total_revenue = float(total_revenue_paise / 100)
    
    month_rev_stmt = select(func.sum(PaymentOrder.amount_paise)).where(PaymentOrder.status == "paid", PaymentOrder.paid_at >= datetime(today.year, today.month, 1, tzinfo=timezone.utc))
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
        total_messages_today=total_messages_today,
        total_tokens_today=total_tokens_today,
        total_revenue=total_revenue,
        revenue_this_month=revenue_this_month,
        active_subscriptions=active_subscriptions,
        total_documents=total_documents
    )


@router.get("/trends", status_code=status.HTTP_200_OK)
async def get_admin_trends(
    days: int = 7,
    current_admin: CurrentAdmin = Depends(require_admin_or_above),
    db: AsyncSession = Depends(get_db),
):
    """Daily signups, revenue and message volume for the dashboard charts."""
    days = max(1, min(days, 30))
    today = date.today()
    start_day = today - timedelta(days=days - 1)
    start_dt = datetime.combine(start_day, datetime.min.time(), tzinfo=timezone.utc)

    user_rows = (
        await db.execute(
            select(func.date(User.created_at).label("day"), func.count(User.id))
            .where(User.created_at >= start_dt)
            .group_by("day")
        )
    ).all()
    payment_rows = (
        await db.execute(
            select(func.date(PaymentOrder.paid_at).label("day"), func.sum(PaymentOrder.amount_paise))
            .where(
                PaymentOrder.status == "paid",
                PaymentOrder.paid_at >= start_dt,
            )
            .group_by("day")
        )
    ).all()
    message_rows = (
        await db.execute(
            select(func.date(Message.created_at).label("day"), func.count(Message.id))
            .where(Message.created_at >= start_dt)
            .group_by("day")
        )
    ).all()

    users = {row[0]: row[1] for row in user_rows if row[0]}
    revenue = {row[0]: float(row[1] or 0) / 100 for row in payment_rows if row[0]}
    messages = {row[0]: row[1] for row in message_rows if row[0]}

    series = []
    for offset in range(days):
        day = start_day + timedelta(days=offset)
        series.append({
            "date": day.isoformat(),
            "label": day.strftime("%d %b"),
            "users": int(users.get(day, 0)),
            "revenue": round(revenue.get(day, 0.0), 2),
            "messages": int(messages.get(day, 0)),
        })

    plan_rows = (
        await db.execute(
            select(Plan.name, Plan.display_name, func.count(UserSubscription.id))
            .join(UserSubscription, UserSubscription.plan_id == Plan.id)
            .where(UserSubscription.status == "active")
            .group_by(Plan.name, Plan.display_name)
        )
    ).all()
    plans = [
        {"name": name, "display_name": display, "count": int(count)}
        for name, display, count in plan_rows
    ]

    return {"days": days, "series": series, "plans": plans}


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

    from app.database import async_session_factory
    from app.services.ai_providers import AIProviderService

    ai_details = {}
    chat_ok = False
    embedding_ok = False
    async with async_session_factory() as session:
        try:
            chat = await AIProviderService.get_default(session, redis_client, "chat")
            ai_details["chat"] = {
                "status": "configured",
                "provider": chat.provider_name,
                "model": chat.model,
                "context_window": chat.context_window,
                "max_output_tokens": chat.max_output_tokens,
            }
            chat_ok = True
        except Exception as exc:
            ai_details["chat"] = {"status": "not_configured", "detail": str(exc)}

        try:
            embedding = await AIProviderService.get_default(
                session, redis_client, "embedding"
            )
            ai_details["embedding"] = {
                "status": "configured",
                "provider": embedding.provider_name,
                "model": embedding.model,
                "dimensions": embedding.embedding_dimensions,
            }
            embedding_ok = True
        except Exception as exc:
            ai_details["embedding"] = {
                "status": "not_configured",
                "detail": str(exc),
            }

    results["services"]["ai"] = {
        "status": "configured" if chat_ok and embedding_ok else (
            "degraded" if chat_ok else "not_configured"
        ),
        "chat": ai_details["chat"],
        "embedding": ai_details["embedding"],
    }
    if not chat_ok or not embedding_ok:
        all_healthy = False

    try:
        started = time.time()
        async with httpx.AsyncClient(timeout=3.0) as client:
            response = await client.get(
                f"{settings.MINIO_ENDPOINT.rstrip('/')}/minio/health/live"
            )
        results["services"]["object_storage"] = {
            "status": "connected" if response.status_code < 400 else "error",
            "latency_ms": round((time.time() - started) * 1000, 1),
            "endpoint": settings.MINIO_ENDPOINT,
            "bucket": settings.MINIO_BUCKET,
        }
        if response.status_code >= 400:
            all_healthy = False
    except Exception as exc:
        results["services"]["object_storage"] = {
            "status": "disconnected",
            "endpoint": settings.MINIO_ENDPOINT,
            "error": "Object storage is unreachable.",
        }
        all_healthy = False

    try:
        from app.services.payments.service import PaymentService

        async with async_session_factory() as session:
            environment = await PaymentService.get_environment(session)
            provider = await PaymentService.get_active_provider(session, environment)
        results["services"]["payments"] = {
            "status": "configured" if provider else "not_configured",
            "environment": environment,
            "provider": provider.display_name if provider else None,
            "mode": getattr(provider, "mode", environment),
        }
    except Exception as exc:
        results["services"]["payments"] = {
            "status": "not_configured",
            "detail": "Payment settings are unavailable.",
        }

    results["services"]["telegram_bot"] = {
        "status": "configured" if settings.TELEGRAM_BOT_TOKEN else "not_configured",
        "username": settings.TELEGRAM_BOT_USERNAME or None,
    }

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
