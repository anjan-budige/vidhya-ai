"""
╔══════════════════════════════════════════════════════════════════╗
║  VIDHYA BOT — Redis Client Pool                                  ║
║  Async Redis with connection pooling for sessions, quotas, cache ║
╚══════════════════════════════════════════════════════════════════╝
"""

import redis.asyncio as aioredis

from app.config import get_settings

settings = get_settings()

# ═══════════════════════════════════════════════════════════════════
# Redis Client (initialized on import, connected on first use)
# ═══════════════════════════════════════════════════════════════════

redis_client: aioredis.Redis = aioredis.from_url(
    settings.REDIS_URL,
    encoding="utf-8",
    decode_responses=True,
    max_connections=settings.REDIS_MAX_CONNECTIONS,
)


# ═══════════════════════════════════════════════════════════════════
# Helper Functions
# ═══════════════════════════════════════════════════════════════════

async def get_redis() -> aioredis.Redis:
    """
    Dependency that provides the Redis client.
    Used via FastAPI's Depends() system.
    """
    return redis_client


async def redis_health_check() -> bool:
    """Check Redis connectivity."""
    try:
        return await redis_client.ping()
    except Exception:
        return False


async def close_redis():
    """Close Redis connection on shutdown."""
    await redis_client.close()


# ═══════════════════════════════════════════════════════════════════
# Redis Key Builders — centralized key naming
# ═══════════════════════════════════════════════════════════════════

class RedisKeys:
    """Centralized Redis key patterns. Prevents typos and ensures consistency."""

    # Sessions
    @staticmethod
    def session(session_id: str) -> str:
        return f"session:{session_id}"

    @staticmethod
    def admin_session(session_id: str) -> str:
        return f"admin_session:{session_id}"

    # Subscription cache
    @staticmethod
    def subscription_cache(user_id: str) -> str:
        return f"sub_cache:{user_id}"

    # Quota counters
    @staticmethod
    def quota_daily(user_id: str, date_str: str) -> str:
        return f"quota:daily:{user_id}:{date_str}"

    @staticmethod
    def quota_monthly(user_id: str, month_str: str) -> str:
        return f"quota:monthly:{user_id}:{month_str}"

    @staticmethod
    def tokens_daily(user_id: str, date_str: str) -> str:
        return f"tokens:daily:{user_id}:{date_str}"

    # Conversations
    @staticmethod
    def active_conversations(user_id: str) -> str:
        return f"conv:active:{user_id}"

    @staticmethod
    def conversation_activity(conv_id: str) -> str:
        return f"conv:last_activity:{conv_id}"

    # Rate limits
    @staticmethod
    def rate_limit_ai(user_id: str) -> str:
        return f"ratelimit:ai:{user_id}"

    @staticmethod
    def rate_limit_login(ip: str) -> str:
        return f"ratelimit:login:{ip}"

    @staticmethod
    def rate_limit_upload(user_id: str) -> str:
        return f"ratelimit:upload:{user_id}"

    # AI cache
    @staticmethod
    def ai_cache(query_hash: str) -> str:
        return f"ai_cache:{query_hash}"

    # Analytics
    @staticmethod
    def analytics_counter(metric: str, date_str: str) -> str:
        return f"analytics:{metric}:{date_str}"
