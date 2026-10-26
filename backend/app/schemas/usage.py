"""Vidhya Bot — Usage Schemas"""

import uuid
from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel

from app.schemas.base import VidhyaBaseModel


class UsageResponse(VidhyaBaseModel):
    """Usage tracking record."""
    id: uuid.UUID
    user_id: uuid.UUID
    period_type: str
    period_date: date
    messages_used: int = 0
    tokens_input: int = 0
    tokens_output: int = 0
    conversations_created: int = 0
    created_at: datetime


class CurrentUsageResponse(BaseModel):
    """Current usage summary for the user dashboard."""
    daily_messages_used: int = 0
    daily_messages_limit: int = 5
    daily_tokens_used: int = 0
    daily_reset_at: Optional[datetime] = None

    monthly_messages_used: int = 0
    monthly_messages_limit: int = 50
    monthly_tokens_used: int = 0
    monthly_reset_at: Optional[datetime] = None

    active_conversations: int = 0
    max_sessions: int = 5
    total_conversations: int = 0

    plan_name: str = "free"
    plan_display_name: str = "Free Plan"

    @property
    def daily_messages_remaining(self) -> int:
        if self.daily_messages_limit == -1:
            return -1  # unlimited
        return max(0, self.daily_messages_limit - self.daily_messages_used)

    @property
    def monthly_messages_remaining(self) -> int:
        if self.monthly_messages_limit == -1:
            return -1
        return max(0, self.monthly_messages_limit - self.monthly_messages_used)


class QuotaCheckResponse(BaseModel):
    """Quick quota check before sending a message."""
    can_send: bool
    reason: Optional[str] = None
    daily_remaining: int = 0
    monthly_remaining: int = 0
