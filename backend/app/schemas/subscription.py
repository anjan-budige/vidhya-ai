"""Vidhya Bot — Subscription Schemas"""

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel

from app.schemas.base import VidhyaBaseModel


class SubscriptionResponse(VidhyaBaseModel):
    """User's current subscription details."""
    id: uuid.UUID
    user_id: uuid.UUID
    plan_id: uuid.UUID
    status: str
    started_at: datetime
    expires_at: Optional[datetime] = None
    plan_snapshot: dict

    total_messages_used: int = 0
    total_tokens_consumed: int = 0
    total_conversations: int = 0

    created_at: datetime
    updated_at: datetime


class SubscriptionWithUsage(SubscriptionResponse):
    """Subscription with current period usage."""
    daily_messages_used: int = 0
    daily_messages_limit: int = 5
    monthly_messages_used: int = 0
    monthly_messages_limit: int = 50
    sessions_used: int = 0
    max_sessions: int = 5
    plan_name: str = "free"
    plan_display_name: str = "Free Plan"


class ActivateFreeRequest(BaseModel):
    """Activate free plan — no payment needed."""
    pass  # Auto-activated on signup


class SubscriptionAdminResponse(SubscriptionResponse):
    """Extended subscription info for admin view."""
    user_telegram_id: Optional[int] = None
    user_first_name: Optional[str] = None
    plan_name: Optional[str] = None

class AssignPlanRequest(BaseModel):
    """Admin request to assign a specific plan to a user."""
    user_id: uuid.UUID
    plan_id: uuid.UUID
