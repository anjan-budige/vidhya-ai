"""Vidhya Bot — User Schemas"""

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

from app.schemas.base import VidhyaBaseModel


class UserResponse(VidhyaBaseModel):
    """User profile response."""
    id: uuid.UUID
    telegram_id: int
    telegram_username: Optional[str] = None
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


class UserListResponse(VidhyaBaseModel):
    """User in admin list view."""
    id: uuid.UUID
    telegram_id: int
    telegram_username: Optional[str] = None
    first_name: str
    last_name: Optional[str] = None
    is_active: bool
    is_banned: bool
    current_plan: Optional[str] = "free"
    total_messages: int = 0
    last_login_at: Optional[datetime] = None
    created_at: datetime
