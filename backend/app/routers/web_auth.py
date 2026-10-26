"""Vidhya Bot — Web Authentication Router"""

import redis.asyncio as aioredis
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.dependencies import get_current_user, get_db, get_redis_client
from app.models.user import User
from app.schemas.auth import (
    ChangePasswordRequest,
    CurrentUser,
    LoginOTPRequest,
    ProfileUpdateRequest,
    RegisterRequest,
    ResendOTPRequest,
    UserForgotPasswordRequest,
    UserLoginRequest,
    UserResetPasswordRequest,
    VerifyEmailRequest,
    WebLoginResponse,
)
from app.services.quota import QuotaService
from app.services.web_auth import WebAuthService
from app.utils.request import get_client_ip

settings = get_settings()
router = APIRouter(prefix="/auth", tags=["Web Authentication"])


def _device_info(request: Request) -> dict:
    return {
        "user_agent": request.headers.get("user-agent"),
        "accept_language": request.headers.get("accept-language"),
    }


def _set_session_cookie(response: Response, token: str, expires_at) -> None:
    response.set_cookie(
        key=settings.SESSION_COOKIE_NAME,
        value=token,
        expires=expires_at,
        path="/",
        secure=settings.SESSION_COOKIE_SECURE,
        httponly=settings.SESSION_COOKIE_HTTPONLY,
        samesite=settings.SESSION_COOKIE_SAMESITE,
    )


async def _plan_name(user_id, db, redis) -> str:
    limits = await QuotaService.get_active_subscription_limits(user_id, db, redis)
    return limits.get("plan_name", "free")


class LinkTelegramRequest(BaseModel):
    telegram_id: int


@router.get("/me", response_model=CurrentUser)
async def me(current_user: CurrentUser = Depends(get_current_user)):
    return current_user


@router.patch("/me", response_model=CurrentUser)
async def update_me(
    payload: ProfileUpdateRequest,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Update the signed-in user's own profile. Changing the email reopens
    verification and sends a new code to the new address.
    """
    user, _ = await WebAuthService.update_profile(db, current_user.id, payload)
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


@router.post("/change-password", status_code=status.HTTP_200_OK)
async def change_password(
    payload: ChangePasswordRequest,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    redis: aioredis.Redis = Depends(get_redis_client),
):
    """Replace the account password after checking the current one."""
    await WebAuthService.change_password(
        db, redis, current_user.id, payload.current_password, payload.new_password
    )
    return {"status": "success", "message": "Password updated."}


@router.post("/api-key/link", status_code=status.HTTP_200_OK)
async def link_api_key(
    payload: LinkTelegramRequest,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    redis: aioredis.Redis = Depends(get_redis_client),
):
    """
    Bind a Telegram id to the API key's user. One Telegram id maps to one
    user; a new login takes over and the previous chat's bot session dies.
    """
    user = (
        await db.execute(select(User).where(User.id == current_user.id))
    ).scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")

    # A Telegram id can only belong to one user
    others = (
        await db.execute(
            select(User).where(
                User.telegram_id == payload.telegram_id,
                User.id != user.id,
            )
        )
    ).scalars().all()
    for other in others:
        other.telegram_id = None
        await redis.delete(f"bot:binding:{other.id}")

    # Moving to a different Telegram id kills the old chat session
    if user.telegram_id and user.telegram_id != payload.telegram_id:
        await redis.delete(f"bot:session:{user.telegram_id}")

    await redis.delete(f"bot:session:{payload.telegram_id}")
    user.telegram_id = payload.telegram_id
    await redis.set(f"bot:binding:{user.id}", str(payload.telegram_id))
    await db.commit()

    return {
        "user_id": str(user.id),
        "telegram_id": payload.telegram_id,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "username": user.username,
        "email": user.email,
    }


@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register(
    payload: RegisterRequest,
    db: AsyncSession = Depends(get_db),
    redis: aioredis.Redis = Depends(get_redis_client),
):
    await WebAuthService.register(db, redis, payload)
    return {
        "status": "verification_sent",
        "message": "Check your email for the 6-digit verification code.",
    }


@router.post("/verify-email", response_model=WebLoginResponse)
async def verify_email(
    payload: VerifyEmailRequest,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
    redis: aioredis.Redis = Depends(get_redis_client),
):
    user, token, expires_at = await WebAuthService.verify_email(
        db,
        redis,
        payload.identifier,
        payload.code,
        get_client_ip(request),
        _device_info(request),
    )
    _set_session_cookie(response, token, expires_at)
    return WebLoginResponse(
        user_id=user.id,
        session_token=token,
        expires_at=expires_at,
        plan_name=await _plan_name(user.id, db, redis),
        message="Email verified.",
    )


@router.post("/resend-otp", status_code=status.HTTP_200_OK)
async def resend_otp(
    payload: ResendOTPRequest,
    db: AsyncSession = Depends(get_db),
    redis: aioredis.Redis = Depends(get_redis_client),
):
    await WebAuthService.resend_verification(db, redis, payload.identifier)
    return {
        "status": "sent",
        "message": "If an unverified account exists, a new code has been sent.",
    }


@router.post("/login", response_model=WebLoginResponse)
async def login(
    payload: UserLoginRequest,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
    redis: aioredis.Redis = Depends(get_redis_client),
):
    result = await WebAuthService.login(
        db,
        redis,
        payload.identifier,
        payload.password,
        get_client_ip(request),
        _device_info(request),
    )

    if result["requires_otp"]:
        return WebLoginResponse(
            requires_otp=True,
            otp_token=result["otp_token"],
            message="Enter the code sent to your email.",
        )

    user = result["user"]
    token = result["session_token"]
    expires_at = result["expires_at"]
    _set_session_cookie(response, token, expires_at)
    return WebLoginResponse(
        user_id=user.id,
        session_token=token,
        expires_at=expires_at,
        plan_name=await _plan_name(user.id, db, redis),
    )


@router.post("/login/verify-otp", response_model=WebLoginResponse)
async def verify_login_otp(
    payload: LoginOTPRequest,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
    redis: aioredis.Redis = Depends(get_redis_client),
):
    user, token, expires_at = await WebAuthService.verify_login_otp(
        db,
        redis,
        payload.otp_token,
        payload.code,
        get_client_ip(request),
        _device_info(request),
    )
    _set_session_cookie(response, token, expires_at)
    return WebLoginResponse(
        user_id=user.id,
        session_token=token,
        expires_at=expires_at,
        plan_name=await _plan_name(user.id, db, redis),
    )


@router.post("/forgot-password", status_code=status.HTTP_200_OK)
async def forgot_password(
    payload: UserForgotPasswordRequest,
    db: AsyncSession = Depends(get_db),
    redis: aioredis.Redis = Depends(get_redis_client),
):
    await WebAuthService.forgot_password(db, redis, payload.email)
    return {
        "status": "success",
        "message": "If the email exists, a reset link has been sent.",
    }


@router.post("/reset-password", status_code=status.HTTP_200_OK)
async def reset_password(
    payload: UserResetPasswordRequest,
    db: AsyncSession = Depends(get_db),
    redis: aioredis.Redis = Depends(get_redis_client),
):
    await WebAuthService.reset_password(db, redis, payload.token, payload.new_password)
    return {"status": "success", "message": "Password updated."}
