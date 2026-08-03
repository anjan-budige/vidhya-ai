"""Vidhya Bot — Message Schemas"""

import uuid
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field

from app.schemas.base import VidhyaBaseModel


class MessageResponse(VidhyaBaseModel):
    """Single message in conversation."""
    id: uuid.UUID
    conversation_id: uuid.UUID
    role: str
    content: str
    token_count: int = 0
    confidence_score: Optional[float] = None
    was_cached: bool = False
    is_in_context: bool = True
    created_at: datetime


class MessageWithRAG(MessageResponse):
    """Message with RAG retrieval details (for debugging/admin)."""
    retrieved_chunks: Optional[dict] = None
    is_summarized: bool = False


class MessageListResponse(BaseModel):
    """Paginated message list."""
    messages: List[MessageResponse]
    total: int
    conversation_id: uuid.UUID
    has_more: bool = False
