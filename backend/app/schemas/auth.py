"""Vidhya Bot — Auth Schemas"""

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

from app.schemas.base import VidhyaBaseModel


# ── Telegram Login ────────────────────────────────────────────────

class TelegramLoginRequest(BaseModel):
    """Telegram login initData from WebApp or widget."""
    init_data: str = Field(..., description="Telegram WebApp initData string")


class TelegramAuthData(BaseModel):
    """Parsed Telegram auth data after HMAC validation."""
    id: int
    first_name: str
    last_name: Optional[str] = None
    username: Optional[str] = None
    photo_url: Optional[str] = None
    auth_date: int
    hash: str


class LoginResponse(VidhyaBaseModel):
    """Response after successful login."""
    user_id: uuid.UUID
    session_token: str
    expires_at: datetime
    is_new_user: bool = False
    plan_name: str = "free"


# ── Admin Login ───────────────────────────────────────────────────

class AdminLoginRequest(BaseModel):
    """Admin login with username + password."""
    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=6)

class AdminForgotPasswordRequest(BaseModel):
    """Request a password reset link."""
    email: str = Field(..., min_length=5, max_length=255)

class AdminResetPasswordRequest(BaseModel):
    """Reset password using token."""
    token: str = Field(..., min_length=10)
    new_password: str = Field(..., min_length=8)

class AdminUpdatePasswordRequest(BaseModel):
    """Update password for an authenticated admin."""
    current_password: str = Field(..., min_length=6)
    new_password: str = Field(..., min_length=8)

class AdminUpdateEmailRequest(BaseModel):
    """Update email for an authenticated admin."""
    email: str = Field(..., min_length=5, max_length=255)

class AdminTOTPVerify(BaseModel):
    """TOTP verification after admin login."""
    session_token: str
    totp_code: str = Field(..., min_length=6, max_length=6)


class AdminLoginResponse(VidhyaBaseModel):
    """Response after admin login."""
    admin_id: uuid.UUID
    session_token: str
    role: str
    requires_totp: bool = False
    expires_at: datetime


class AdminRefreshResponse(VidhyaBaseModel):
    """Response after session refresh."""
    session_token: str
    expires_at: datetime


# ── Session Info ──────────────────────────────────────────────────

class SessionInfo(VidhyaBaseModel):
    """Current session details."""
    session_id: uuid.UUID
    user_id: uuid.UUID
    ip_address: Optional[str] = None
    device_info: Optional[dict] = None
    created_at: datetime
    last_accessed_at: datetime
    expires_at: datetime


# ── Current User ──────────────────────────────────────────────────

class CurrentUser(VidhyaBaseModel):
    """User data attached to authenticated requests."""
    id: uuid.UUID
    telegram_id: int
    first_name: str
    last_name: Optional[str] = None
    telegram_username: Optional[str] = None
    is_active: bool
    is_banned: bool


class CurrentAdmin(VidhyaBaseModel):
    """Admin data attached to authenticated requests."""
    id: uuid.UUID
    username: str
    role: str
    is_active: bool
