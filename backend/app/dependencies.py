import uuid
from typing import AsyncGenerator, Optional

import redis.asyncio as aioredis
from fastapi import Cookie, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.database import async_session_factory
from app.models.admin import Admin
from app.models.user import User
from app.redis_client import RedisKeys, redis_client
from app.schemas.auth import CurrentAdmin, CurrentUser
from app.schemas.base import PaginationParams



def get_app_settings() -> Settings:
    """Provide cached settings instance."""
    return get_settings()



async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Provide a database session with auto-commit/rollback.
    
    Usage:
        @router.get("/")
        async def endpoint(db: AsyncSession = Depends(get_db)):
            ...
    """
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()



async def get_redis_client() -> aioredis.Redis:
    """Provide the Redis client."""
    return redis_client



async def get_session_token(
    request: Request,
    vidhya_session: Optional[str] = Cookie(default=None),
) -> str:
    """
    Extract session token from Authorization header or cookie.
    IMPORTANT: Authorization header is checked FIRST because the bot's shared
    httpx client accumulates cookies from all users' login responses, causing
    cross-user session leaks if cookies are checked first.
    """
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        return auth_header[7:]

    # Fall back to cookie (for browser / frontend sessions)
    if vidhya_session:
        return vidhya_session

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentication required. No session token provided.",
    )


def _token_from_request(
    request: Request, cookie: Optional[str]
) -> Optional[str]:
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        return auth_header[7:]
    return cookie


async def get_current_user(
    request: Request,
    vidhya_session: Optional[str] = Cookie(default=None),
    redis: aioredis.Redis = Depends(get_redis_client),
    db: AsyncSession = Depends(get_db),
) -> CurrentUser:
    """
    Resolve the caller from an X-API-Key header, a Bearer token, or the
    session cookie. API keys are checked first so bot traffic never needs
    a cookie jar.
    """
    api_key = request.headers.get("X-API-Key")
    if api_key:
        from app.services.api_keys import ApiKeyService
        from app.utils.internal_auth import is_telegram_bot_request

        if not is_telegram_bot_request(request.headers):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="API keys are accepted only from the connected Telegram bot.",
            )
        return await ApiKeyService.authenticate(db, redis, api_key)

    token = _token_from_request(request, vidhya_session)
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required. No session token provided.",
        )

    session_data = await redis.hgetall(RedisKeys.session(token))
    if not session_data:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session expired or invalid. Please log in again.",
        )

    user_id = session_data.get("user_id")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid session data.",
        )

    user = (
        await db.execute(select(User).where(User.id == uuid.UUID(user_id)))
    ).scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found.",
        )

    if user.is_banned:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Account banned: {user.ban_reason or 'Contact support.'}",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is deactivated.",
        )

    return CurrentUser(
        id=user.id,
        telegram_id=user.telegram_id,
        username=user.username,
        email=user.email,
        mobile=user.mobile,
        first_name=user.first_name,
        last_name=user.last_name,
        telegram_username=user.telegram_username,
        auth_provider=user.auth_provider,
        email_verified_at=user.email_verified_at,
        is_active=user.is_active,
        is_banned=user.is_banned,
    )


async def get_current_user_optional(
    request: Request,
    vidhya_session: Optional[str] = Cookie(default=None),
    redis: aioredis.Redis = Depends(get_redis_client),
    db: AsyncSession = Depends(get_db),
) -> Optional[CurrentUser]:
    """
    Like get_current_user but returns None if not authenticated.
    Used for endpoints that work with or without auth.
    """
    api_key = request.headers.get("X-API-Key")
    if api_key:
        try:
            from app.services.api_keys import ApiKeyService
            from app.utils.internal_auth import is_telegram_bot_request

            if not is_telegram_bot_request(request.headers):
                return None
            return await ApiKeyService.authenticate(db, redis, api_key)
        except HTTPException:
            return None

    token = _token_from_request(request, vidhya_session)
    if not token:
        return None

    try:
        session_key = RedisKeys.session(token)
        session_data = await redis.hgetall(session_key)
        if not session_data or "user_id" not in session_data:
            return None

        result = await db.execute(
            select(User).where(User.id == uuid.UUID(session_data["user_id"]))
        )
        user = result.scalar_one_or_none()
        if not user or user.is_banned or not user.is_active:
            return None

        return CurrentUser(
            id=user.id,
            telegram_id=user.telegram_id,
            username=user.username,
            email=user.email,
            mobile=user.mobile,
            first_name=user.first_name,
            last_name=user.last_name,
            telegram_username=user.telegram_username,
            auth_provider=user.auth_provider,
            email_verified_at=user.email_verified_at,
            is_active=user.is_active,
            is_banned=user.is_banned,
        )
    except Exception:
        return None



async def get_admin_session_token(
    request: Request,
    vidhya_admin_session: Optional[str] = Cookie(default=None),
) -> str:
    """Extract admin session token from cookie or header."""
    if vidhya_admin_session:
        return vidhya_admin_session

    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        return auth_header[7:]

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Admin authentication required.",
    )


async def get_current_admin(
    session_token: str = Depends(get_admin_session_token),
    redis: aioredis.Redis = Depends(get_redis_client),
    db: AsyncSession = Depends(get_db),
) -> CurrentAdmin:
    """
    Validate admin session and return admin data.
    
    Raises:
        401: Invalid or expired admin session
        403: Admin is locked or inactive
    """
    session_key = RedisKeys.admin_session(session_token)
    session_data = await redis.hgetall(session_key)

    if not session_data:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Admin session expired. Please log in again.",
        )

    admin_id = session_data.get("admin_id")
    if not admin_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid admin session.",
        )

    # Password verification alone must never authorize an admin when TOTP is
    # enabled. The pre-auth token is valid only for /admin/totp/verify.
    if session_data.get("is_pre_auth") != "false":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Complete two-factor verification to continue.",
        )

    result = await db.execute(
        select(Admin).where(Admin.id == uuid.UUID(admin_id))
    )
    admin = result.scalar_one_or_none()

    if not admin:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Admin not found.",
        )

    if not admin.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin account is deactivated.",
        )

    if admin.is_locked:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin account is temporarily locked due to failed login attempts.",
        )

    return CurrentAdmin(
        id=admin.id,
        username=admin.username,
        role=admin.role,
        is_active=admin.is_active,
    )


async def require_superadmin(
    admin: CurrentAdmin = Depends(get_current_admin),
) -> CurrentAdmin:
    """Require superadmin role."""
    if admin.role != "superadmin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Superadmin access required.",
        )
    return admin


async def require_admin_or_above(
    admin: CurrentAdmin = Depends(get_current_admin),
) -> CurrentAdmin:
    """Require admin or superadmin role (not viewer)."""
    if admin.role == "viewer":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin or superadmin access required. Viewer role insufficient.",
        )
    return admin



async def require_billing_enabled(
    db: AsyncSession = Depends(get_db),
) -> None:
    """
    Block billing mutations while the platform is in Free mode.

    Reads from Postgres (not the Redis cache) so a stale cache can never
    let a request through after the mode has been switched.
    """
    from app.services.platform import PAID, PlatformConfigService

    mode = await PlatformConfigService.get_mode_fresh(db)
    if mode != PAID:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Billing is disabled on this platform (Free mode).",
        )



def get_pagination(page: int = 1, page_size: int = 20) -> PaginationParams:
    """Parse pagination query params."""
    return PaginationParams(
        page=max(1, page),
        page_size=min(max(1, page_size), 100),
    )
