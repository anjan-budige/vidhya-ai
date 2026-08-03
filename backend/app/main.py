"""
╔══════════════════════════════════════════════════════════════════╗
║  VIDHYA BOT — FastAPI Application Entry Point                    ║
║  Phase 2: Config, Database, Redis, Models, Schemas, Dependencies ║
╚══════════════════════════════════════════════════════════════════╝
"""

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

# Import all models to register them with SQLAlchemy metadata
import app.models  # noqa: F401

# Import versioned routers
from app.routers import auth, plans, subscriptions, payments, conversations, ai, documents, analytics, users, audit, admin_settings
from app.workers.celery_app import celery_app

# ═══════════════════════════════════════════════════════════════════
# Configuration
# ═══════════════════════════════════════════════════════════════════

settings = get_settings()

# ═══════════════════════════════════════════════════════════════════
# Logging
# ═══════════════════════════════════════════════════════════════════

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

# ═══════════════════════════════════════════════════════════════════
# Startup Time Tracking
# ═══════════════════════════════════════════════════════════════════

startup_time: float = 0


# ═══════════════════════════════════════════════════════════════════
# Lifespan — startup/shutdown hooks
# ═══════════════════════════════════════════════════════════════════

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifecycle — connect/disconnect services."""
    global startup_time
    startup_time = time.time()

    logger.info("vidhya.startup", env=settings.ENV, debug=settings.DEBUG)

    # ── Connect Redis ─────────────────────────────────────────────
    try:
        await redis_client.ping()
        logger.info("redis.connected", url=settings.REDIS_URL)
    except Exception as e:
        logger.error("redis.connection_failed", error=str(e))

    # ── Test Database Connection ──────────────────────────────────
    try:
        async with engine.begin() as conn:
            result = await conn.execute(text("SELECT 1"))
            result.scalar()
        logger.info("postgres.connected")
    except Exception as e:
        logger.error("postgres.connection_failed", error=str(e))

    # ── Verify pgvector extension ─────────────────────────────────
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

    # ── Auto-Heal Vector Dimensions (Mistral 1024) ────────────────
    try:
        async with engine.begin() as conn:
            await conn.execute(text("ALTER TABLE document_chunks ALTER COLUMN embedding TYPE vector(1024);"))
            logger.info("pgvector.auto_healed", dimensions=1024, msg="Successfully resized embedding column")
    except Exception as e:
        # Ignore errors if the table doesn't exist yet or is already correct
        logger.debug("pgvector.auto_heal_skipped", error=str(e))

    # ── Auto-Heal Documents Table Progress Column ─────────────────
    try:
        async with engine.begin() as conn:
            await conn.execute(text("ALTER TABLE documents ADD COLUMN IF NOT EXISTS processed_chunks INTEGER DEFAULT 0;"))
            logger.info("db.documents.progress_column_ensured")
    except Exception as e:
        logger.warning("db.documents.progress_column_failed", error=str(e))

    # ── Verify Plans Seeded ───────────────────────────────────────
    try:
        async with async_session_factory() as session:
            result = await session.execute(text("SELECT COUNT(*) FROM plans"))
            plan_count = result.scalar()
            logger.info("plans.count", count=plan_count)
            if plan_count == 0:
                logger.warning("plans.empty", hint="Plans table exists but has no data")
    except Exception as e:
        logger.warning("plans.check_failed", error=str(e))

    # ── Verify / Seed Admin ───────────────────────────────────────
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
                    
                    # Send welcome email
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

    # ── Shutdown ──────────────────────────────────────────────────
    logger.info("vidhya.shutdown")
    await close_redis()
    logger.info("redis.disconnected")
    await dispose_engine()
    logger.info("postgres.disconnected")


# ═══════════════════════════════════════════════════════════════════
# FastAPI Application
# ═══════════════════════════════════════════════════════════════════

app = FastAPI(
    title=f"{settings.APP_NAME} API",
    description="AI-powered educational assistant platform with subscription management",
    version="3.0.0",
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None,
    default_response_class=ORJSONResponse,
    lifespan=lifespan,
)

# ── CORS Middleware ───────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["X-Request-ID"],
)

# ── Rate Limit Middleware ─────────────────────────────────────────
app.add_middleware(RateLimitMiddleware)

# ── CSRF Middleware ───────────────────────────────────────────────
app.add_middleware(CSRFMiddleware)

# ── Include Routers (Versioned Prefix: /api/v1) ───────────────────
app.include_router(auth.router, prefix="/api/v1")
app.include_router(plans.router, prefix="/api/v1")
app.include_router(subscriptions.router, prefix="/api/v1")
app.include_router(payments.router, prefix="/api/v1")
app.include_router(conversations.router, prefix="/api/v1")
app.include_router(ai.router, prefix="/api/v1")
app.include_router(documents.router, prefix="/api/v1")
app.include_router(analytics.router, prefix="/api/v1")
app.include_router(users.router, prefix="/api/v1")
app.include_router(audit.router, prefix="/api/v1")
app.include_router(admin_settings.router, prefix="/api/v1/admin/settings", tags=["Admin Settings"])

# ═══════════════════════════════════════════════════════════════════
# Health Check Endpoints
# ═══════════════════════════════════════════════════════════════════

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

    # ── Check table count ─────────────────────────────────────────
    # Removed for security (do not leak DB schema size)

    # ── Redis ─────────────────────────────────────────────────────
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
                results["services"]["mistral"] = {
                    "status": "connected",
                    "latency_ms": latency_ms,
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

    # ── MinIO ─────────────────────────────────────────────────────
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

    # ── Overall status ────────────────────────────────────────────
    results["status"] = "healthy" if all_healthy else "degraded"

    return results
