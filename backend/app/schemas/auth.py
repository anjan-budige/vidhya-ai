"""Vidhya Bot — Auth Schemas"""

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

from app.schemas.base import VidhyaBaseModel



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



class SessionInfo(VidhyaBaseModel):
    """Current session details."""
    session_id: uuid.UUID
    user_id: uuid.UUID
    ip_address: Optional[str] = None
    device_info: Optional[dict] = None
    created_at: datetime
    last_accessed_at: datetime
    expires_at: datetime



class CurrentUser(VidhyaBaseModel):
    """User data attached to authenticated requests."""
    id: uuid.UUID
    telegram_id: Optional[int] = None
    username: Optional[str] = None
    email: Optional[str] = None
    mobile: Optional[str] = None
    first_name: str
    last_name: Optional[str] = None
    telegram_username: Optional[str] = None
    auth_provider: str = "telegram"
    email_verified_at: Optional[datetime] = None
    is_active: bool
    is_banned: bool



class RegisterRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=30, pattern=r"^[a-z0-9_]+$")
    name: str = Field(..., min_length=2, max_length=100)
    email: str = Field(..., min_length=5, max_length=255)
    mobile: str = Field(..., min_length=7, max_length=20)
    password: str = Field(..., min_length=8, max_length=128)


class VerifyEmailRequest(BaseModel):
    identifier: str = Field(..., min_length=3, max_length=255)
    code: str = Field(..., min_length=6, max_length=6)


class ResendOTPRequest(BaseModel):
    identifier: str = Field(..., min_length=3, max_length=255)


class UserLoginRequest(BaseModel):
    identifier: str = Field(..., min_length=3, max_length=255)
    password: str = Field(..., min_length=1, max_length=128)


class LoginOTPRequest(BaseModel):
    otp_token: str = Field(..., min_length=10)
    code: str = Field(..., min_length=6, max_length=6)


class UserForgotPasswordRequest(BaseModel):
    email: str = Field(..., min_length=5, max_length=255)


class UserResetPasswordRequest(BaseModel):
    token: str = Field(..., min_length=10)
    new_password: str = Field(..., min_length=8, max_length=128)


class ProfileUpdateRequest(BaseModel):
    """Self-service profile edit; omitted fields keep their current value."""
    name: Optional[str] = Field(None, min_length=2, max_length=100)
    username: Optional[str] = Field(
        None, min_length=3, max_length=30, pattern=r"^[a-z0-9_]+$"
    )
    email: Optional[str] = Field(None, min_length=5, max_length=255)
    mobile: Optional[str] = Field(None, min_length=7, max_length=20)


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(..., min_length=1, max_length=128)
    new_password: str = Field(..., min_length=8, max_length=128)


class WebLoginResponse(VidhyaBaseModel):
    requires_otp: bool = False
    otp_token: Optional[str] = None
    user_id: Optional[uuid.UUID] = None
    session_token: Optional[str] = None
    expires_at: Optional[datetime] = None
    plan_name: str = "free"
    is_new_user: bool = False
    message: Optional[str] = None


class CurrentAdmin(VidhyaBaseModel):
    """Admin data attached to authenticated requests."""
    id: uuid.UUID
    username: str
    role: str
    is_active: bool
