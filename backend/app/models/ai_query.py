"""
Vidhya Bot — AI Query Model

Audit trail for every AI query — tracks query text, response,
RAG retrieval details, token usage, and performance metrics.
"""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Boolean, DateTime, Float, Integer, String, Text, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.base import UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.conversation import Conversation
    from app.models.message import Message
    from app.models.user import User


class AIQuery(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "ai_queries"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    conversation_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    message_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("messages.id", ondelete="CASCADE"),
        nullable=True,
    )

    query_text: Mapped[str] = mapped_column(Text, nullable=False)
    response_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    chunks_retrieved: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0"
    )
    retrieval_score: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True
    )

    tokens_input: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0"
    )
    tokens_output: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0"
    )
    total_tokens: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0"
    )

    response_time_ms: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True
    )
    model_used: Mapped[Optional[str]] = mapped_column(
        String(50), nullable=True
    )
    was_cached: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false"
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default="now()", nullable=False, index=True
    )

    def __repr__(self) -> str:
        query_preview = self.query_text[:50] + "..." if len(self.query_text) > 50 else self.query_text
        return (
            f"<AIQuery(user={self.user_id}, tokens={self.total_tokens}, "
            f"time={self.response_time_ms}ms, query='{query_preview}')>"
        )
