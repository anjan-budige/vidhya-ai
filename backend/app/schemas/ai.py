"""Vidhya Bot — AI Chat Schemas"""

import uuid
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field

from app.schemas.base import VidhyaBaseModel


class AIChatRequest(BaseModel):
    """User sends a message to AI."""
    message: str = Field(..., min_length=1, max_length=4000)
    conversation_id: Optional[uuid.UUID] = None  # None = use active or create new


class AIChatStreamEvent(BaseModel):
    """SSE streaming event for AI chat response."""
    event: str  # "token" | "done" | "error" | "metadata"
    data: str = ""
    conversation_id: Optional[uuid.UUID] = None
    message_id: Optional[uuid.UUID] = None


class AIChatResponse(VidhyaBaseModel):
    """Non-streaming AI chat response."""
    conversation_id: uuid.UUID
    message_id: uuid.UUID
    response: str
    tokens_used: int = 0
    response_time_ms: int = 0
    was_cached: bool = False
    sources: Optional[List[dict]] = None  # RAG source references


class AIQuotaResponse(BaseModel):
    """Current AI quota for the user."""
    can_send: bool
    daily_messages_used: int = 0
    daily_messages_limit: int = 5
    monthly_messages_used: int = 0
    monthly_messages_limit: int = 50
    daily_remaining: int = 5
    monthly_remaining: int = 50
    active_conversations: int = 0
    max_active_conversations: int = 1
    plan_name: str = "free"
    next_daily_reset: Optional[datetime] = None


class AIHistoryItem(VidhyaBaseModel):
    """Single AI query in history."""
    id: uuid.UUID
    query_text: str
    response_text: Optional[str] = None
    tokens_input: int = 0
    tokens_output: int = 0
    total_tokens: int = 0
    response_time_ms: Optional[int] = None
    model_used: Optional[str] = None
    was_cached: bool = False
    created_at: datetime
