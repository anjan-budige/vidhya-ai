"""Vidhya Bot — Conversation Schemas"""

import uuid
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field

from app.schemas.base import VidhyaBaseModel


class ConversationCreateRequest(BaseModel):
    """Start a new conversation."""
    title: Optional[str] = Field(None, max_length=255)


class ConversationUpdateRequest(BaseModel):
    """Rename a saved conversation."""
    title: str = Field(..., min_length=1, max_length=120)


class ConversationResponse(VidhyaBaseModel):
    """Conversation details."""
    id: uuid.UUID
    user_id: uuid.UUID
    title: Optional[str] = None
    total_messages: int = 0
    total_tokens_used: int = 0

    max_context_tokens: int
    memory_retention_days: int

    summary_text: Optional[str] = None
    messages_since_summary: int = 0

    started_at: datetime
    last_activity_at: datetime
    created_at: datetime


class ConversationListResponse(VidhyaBaseModel):
    """Conversation in list view (lighter)."""
    id: uuid.UUID
    title: Optional[str] = None
    total_messages: int = 0
    started_at: datetime
    last_activity_at: datetime


class ConversationAdminResponse(ConversationResponse):
    """Extended conversation info for admin view."""
    user_telegram_id: Optional[int] = None
    user_first_name: Optional[str] = None
    subscription_id: Optional[uuid.UUID] = None
