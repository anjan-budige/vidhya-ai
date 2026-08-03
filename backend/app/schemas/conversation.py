"""Vidhya Bot — Conversation Schemas"""

import uuid
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field

from app.schemas.base import VidhyaBaseModel


class ConversationCreateRequest(BaseModel):
    """Start a new conversation."""
    title: Optional[str] = Field(None, max_length=255)


class ConversationResponse(VidhyaBaseModel):
    """Conversation details."""
    id: uuid.UUID
    user_id: uuid.UUID
    title: Optional[str] = None
    status: str
    total_messages: int = 0
    total_tokens_used: int = 0

    max_context_messages: int
    max_context_tokens: int
    conversation_timeout_min: int
    memory_retention_days: int

    summary_text: Optional[str] = None
    messages_since_summary: int = 0

    started_at: datetime
    last_activity_at: datetime
    closed_at: Optional[datetime] = None
    auto_close_reason: Optional[str] = None
    created_at: datetime


class ConversationListResponse(VidhyaBaseModel):
    """Conversation in list view (lighter)."""
    id: uuid.UUID
    title: Optional[str] = None
    status: str
    total_messages: int = 0
    started_at: datetime
    last_activity_at: datetime
    closed_at: Optional[datetime] = None


class ActiveConversationsResponse(BaseModel):
    """Active conversations for a user."""
    conversations: List[ConversationListResponse]
    active_count: int
    max_active: int


class ConversationAdminResponse(ConversationResponse):
    """Extended conversation info for admin view."""
    user_telegram_id: Optional[int] = None
    user_first_name: Optional[str] = None
    subscription_id: Optional[uuid.UUID] = None
