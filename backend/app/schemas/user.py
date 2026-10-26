"""Vidhya Bot — User Schemas"""

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

from app.schemas.base import VidhyaBaseModel


class UserResponse(VidhyaBaseModel):
    """User profile response."""
    id: uuid.UUID
    telegram_id: Optional[int] = None
    telegram_username: Optional[str] = None
    username: Optional[str] = None
    email: Optional[str] = None
    mobile: Optional[str] = None
    auth_provider: str = "telegram"
    first_name: str
    last_name: Optional[str] = None
    photo_url: Optional[str] = None
    language_code: str = "en"
    is_active: bool
    is_banned: bool
    last_login_at: Optional[datetime] = None
    created_at: datetime


class UserProfileResponse(UserResponse):
    """Extended profile with subscription info."""
    current_plan: Optional[str] = "free"
    subscription_status: Optional[str] = None
    subscription_expires_at: Optional[datetime] = None


class UserUpdateRequest(BaseModel):
    """Admin update user fields."""
    is_active: Optional[bool] = None
    is_banned: Optional[bool] = None
    ban_reason: Optional[str] = None


class UserBanRequest(BaseModel):
    """Ban a user with reason."""
    reason: str = Field(..., min_length=5, max_length=500)


class AdminCreateUserRequest(BaseModel):
    """Admin creates a user from the dashboard."""
    username: str = Field(..., min_length=3, max_length=30, pattern=r"^[a-z0-9_]+$")
    name: str = Field(..., min_length=2, max_length=100)
    email: str = Field(..., min_length=5, max_length=255)
    mobile: str = Field(..., min_length=7, max_length=20)
    password: Optional[str] = Field(None, min_length=8, max_length=128)


class ApiKeyInfo(BaseModel):
    id: uuid.UUID
    label: str
    key_prefix: str
    is_enabled: bool
    last_used_at: Optional[datetime] = None
    revoked_at: Optional[datetime] = None
    created_at: datetime


class ApiKeyGenerated(BaseModel):
    key: str
    info: ApiKeyInfo


class ApiKeyUpdateRequest(BaseModel):
    is_enabled: Optional[bool] = None
    rotate: bool = False
    label: Optional[str] = Field(None, max_length=50)


class AdminUpdateUserRequest(BaseModel):
    """Admin edits a user's profile details."""
    name: Optional[str] = Field(None, min_length=2, max_length=100)
    username: Optional[str] = Field(None, min_length=3, max_length=30)
    email: Optional[str] = Field(None, min_length=5, max_length=255)
    mobile: Optional[str] = Field(None, min_length=7, max_length=20)


class AdminCreateUserResponse(VidhyaBaseModel):
    user: UserResponse
    setup_email_sent: bool


class UserListResponse(VidhyaBaseModel):
    """User in admin list view."""
    id: uuid.UUID
    telegram_id: Optional[int] = None
    telegram_username: Optional[str] = None
    username: Optional[str] = None
    email: Optional[str] = None
    mobile: Optional[str] = None
    auth_provider: str = "telegram"
    first_name: str
    last_name: Optional[str] = None
    is_active: bool
    is_banned: bool
    current_plan: Optional[str] = "free"
    total_messages: int = 0
    last_login_at: Optional[datetime] = None
    created_at: datetime
