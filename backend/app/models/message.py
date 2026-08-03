"""
Vidhya Bot — Message Model

Individual chat messages with role tracking, token counts,
RAG metadata, and context window status.
"""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Boolean, DateTime, Float, Integer, String, Text, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.base import UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.conversation import Conversation
    from app.models.user import User


class Message(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "messages"

    # ── Foreign Keys ──────────────────────────────────────────────
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=False,
    )

    # ── Message Content ───────────────────────────────────────────
    role: Mapped[str] = mapped_column(
        String(20), nullable=False
    )  # 'user' | 'assistant' | 'system'
    content: Mapped[str] = mapped_column(Text, nullable=False)
    token_count: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0"
    )

    # ── RAG Metadata ──────────────────────────────────────────────
    retrieved_chunks: Mapped[Optional[dict]] = mapped_column(
        JSONB, nullable=True
    )  # chunk references used for this response
    confidence_score: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True
    )
    was_cached: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false"
    )

    # ── Context Window Status ─────────────────────────────────────
    is_in_context: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default="true"
    )  # within rolling window?
    is_summarized: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false"
    )  # rolled into summary?

    # ── Timestamps ────────────────────────────────────────────────
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default="now()", nullable=False
    )

    # ── Relationships ─────────────────────────────────────────────
    conversation: Mapped["Conversation"] = relationship(back_populates="messages")
    user: Mapped["User"] = relationship(back_populates="messages")

    def __repr__(self) -> str:
        content_preview = self.content[:50] + "..." if len(self.content) > 50 else self.content
        return f"<Message(role={self.role}, tokens={self.token_count}, content='{content_preview}')>"

    @property
    def is_user_message(self) -> bool:
        return self.role == "user"

    @property
    def is_assistant_message(self) -> bool:
        return self.role == "assistant"

    @property
    def is_system_message(self) -> bool:
        return self.role == "system"
