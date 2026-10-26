import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone

import httpx
import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import ORJSONResponse
from sqlalchemy import text

from app.config import get_settings
from app.database import engine, async_session_factory, dispose_engine
from app.redis_client import redis_client, close_redis
from app.middleware.rate_limit import RateLimitMiddleware
from app.middleware.csrf import CSRFMiddleware

import app.models  # noqa: F401

from app.routers import auth, plans, subscriptions, payments, payments_admin, conversations, ai, documents, analytics, users, audit, platform, web_auth, ai_admin
from app.workers.celery_app import celery_app


settings = get_settings()


structlog.configure(
    processors=[
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.StackInfoRenderer(),
        structlog.dev.ConsoleRenderer() if settings.DEBUG else structlog.processors.JSONRenderer(),
    ],
    wrapper_class=structlog.make_filtering_bound_logger(
        structlog.get_config().get("min_level", 20)
    ),
    context_class=dict,
    logger_factory=structlog.PrintLoggerFactory(),
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger()


startup_time: float = 0


# Lifespan — startup/shutdown hooks

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifecycle — connect/disconnect services."""
    global startup_time
    startup_time = time.time()

    logger.info("vidhya.startup", env=settings.ENV, debug=settings.DEBUG)

    try:
        await redis_client.ping()
        logger.info("redis.connected", url=settings.REDIS_URL)
    except Exception as e:
        logger.error("redis.connection_failed", error=str(e))

    try:
        async with engine.begin() as conn:
            result = await conn.execute(text("SELECT 1"))
            result.scalar()
        logger.info("postgres.connected")
    except Exception as e:
        logger.error("postgres.connection_failed", error=str(e))

    try:
        async with engine.begin() as conn:
            result = await conn.execute(
                text("SELECT extname FROM pg_extension WHERE extname = 'vector'")
            )
            ext = result.scalar()
            if ext:
                logger.info("pgvector.enabled")
            else:
                logger.warning("pgvector.not_found", hint="Run: CREATE EXTENSION vector;")
    except Exception as e:
        logger.warning("pgvector.check_failed", error=str(e))

    try:
        async with engine.begin() as conn:
            await conn.execute(text("ALTER TABLE documents ADD COLUMN IF NOT EXISTS processed_chunks INTEGER DEFAULT 0;"))
            logger.info("db.documents.progress_column_ensured")
    except Exception as e:
        logger.warning("db.documents.progress_column_failed", error=str(e))

    try:
        async with async_session_factory() as session:
            result = await session.execute(text("SELECT COUNT(*) FROM plans"))
            plan_count = result.scalar()
            logger.info("plans.count", count=plan_count)
            if plan_count == 0:
                logger.warning("plans.empty", hint="Plans table exists but has no data")
    except Exception as e:
        logger.warning("plans.check_failed", error=str(e))

    try:
        from app.models.admin import Admin
        from app.services.auth import AdminAuthService
        from app.utils.email import send_deployment_welcome_email
        from sqlalchemy import select
        
        async with async_session_factory() as session:
            result = await session.execute(select(Admin))
            admins = result.scalars().all()
            
            if not admins:
                logger.info("admin.not_found", msg="No admins exist, seeding default admin")
                try:
                    new_admin = Admin(
                        username=settings.ADMIN_DEFAULT_USERNAME,
                        password_hash=AdminAuthService.hash_password(settings.ADMIN_DEFAULT_PASSWORD),
                        email=settings.SUPERADMIN_EMAIL,
                        totp_secret=settings.ADMIN_TOTP_SECRET if settings.ADMIN_TOTP_ENABLED else None,
                        totp_enabled=settings.ADMIN_TOTP_ENABLED,
                        role="superadmin"
                    )
                    session.add(new_admin)
                    await session.commit()
                    logger.info("admin.seeded", username=new_admin.username)
                    
                    if settings.SUPERADMIN_EMAIL:
                        await send_deployment_welcome_email(
                            to_email=settings.SUPERADMIN_EMAIL,
                            username=settings.ADMIN_DEFAULT_USERNAME,
                            raw_password=settings.ADMIN_DEFAULT_PASSWORD
                        )
                except Exception as e:
                    # Ignore unique violations if another worker seeded it first
                    if "duplicate key value violates unique constraint" in str(e):
                        logger.info("admin.seed_skipped", msg="Another worker seeded the admin first")
                    else:
                        logger.error("admin.seeding_failed", error=str(e))
            else:
                logger.info("admin.exists", count=len(admins))
    except Exception as e:
        logger.error("admin.check_failed", error=str(e))

    logger.info(
        "vidhya.ready",
        startup_seconds=round(time.time() - startup_time, 2),
    )

    yield

    logger.info("vidhya.shutdown")
    await close_redis()
    logger.info("redis.disconnected")
    await dispose_engine()
    logger.info("postgres.disconnected")



app = FastAPI(
    title=f"{settings.APP_NAME} API",
    description="AI-powered educational assistant platform with subscription management",
    version="3.0.0",
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None,
    default_response_class=ORJSONResponse,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["X-Request-ID"],
)

app.add_middleware(RateLimitMiddleware)

app.add_middleware(CSRFMiddleware)

app.include_router(auth.router, prefix="/api/v1")
app.include_router(web_auth.router, prefix="/api/v1")
app.include_router(plans.router, prefix="/api/v1")
app.include_router(subscriptions.router, prefix="/api/v1")
app.include_router(payments.router, prefix="/api/v1")
app.include_router(payments_admin.router, prefix="/api/v1")
app.include_router(conversations.router, prefix="/api/v1")
app.include_router(ai.router, prefix="/api/v1")
app.include_router(documents.router, prefix="/api/v1")
app.include_router(analytics.router, prefix="/api/v1")
app.include_router(users.router, prefix="/api/v1")
app.include_router(audit.router, prefix="/api/v1")
app.include_router(platform.public_router, prefix="/api/v1")
app.include_router(platform.admin_router, prefix="/api/v1")
app.include_router(ai_admin.router, prefix="/api/v1")


@app.get("/health", tags=["Health"])
async def health_check():
    """Simple health check — returns 200 if the server is running."""
    return {
        "status": "healthy",
        "service": settings.APP_NAME,
        "version": "3.0.0",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@app.get("/health/detailed", tags=["Health"])
async def detailed_health_check():
    """
    Detailed health check — verifies connectivity to all infrastructure services.
    Returns individual status for: PostgreSQL, Redis, Ollama, MinIO.
    """
    results = {
        "status": "healthy",
        "service": settings.APP_NAME,
        "version": "3.0.0",
        "environment": settings.ENV,
        "uptime_seconds": round(time.time() - startup_time, 2),
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

    # Removed for security (do not leak DB schema size)

    try:
        start = time.time()
        pong = await redis_client.ping()
        latency_ms = round((time.time() - start) * 1000, 1)
        results["services"]["redis"] = {
            "status": "connected" if pong else "error",
            "latency_ms": latency_ms,
        }
    except Exception as e:
        results["services"]["redis"] = {
            "status": "disconnected",
            "error": str(e),
        }
        all_healthy = False

    try:
        from app.services.ai_providers import AIConfigError, AIProviderService

        async with async_session_factory() as session:
            chat = await AIProviderService.get_default(session, redis_client, "chat")
        results["services"]["ai"] = {
            "status": "configured",
            "provider": chat.provider_name,
            "model": chat.model,
        }
    except AIConfigError as e:
        results["services"]["ai"] = {
            "status": "not_configured",
            "detail": str(e),
        }
        all_healthy = False
    except Exception as e:
        results["services"]["ai"] = {
            "status": "error",
            "error": str(e),
        }
        all_healthy = False

    try:
        start = time.time()
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(f"{settings.MINIO_ENDPOINT}/minio/health/live")
            latency_ms = round((time.time() - start) * 1000, 1)

            results["services"]["minio"] = {
                "status": "connected" if response.status_code == 200 else "error",
                "latency_ms": latency_ms,
                "http_status": response.status_code,
            }
            if response.status_code != 200:
                all_healthy = False
    except Exception as e:
        results["services"]["minio"] = {
            "status": "disconnected",
            "error": str(e),
        }
        all_healthy = False

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
