"""
Vidhya Bot — Conversation Model

Chat conversation lifecycle with plan-bound context limits,
auto-summarization support, and timeout tracking.
"""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import BigInteger, DateTime, Integer, String, Text, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.base import UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.message import Message
    from app.models.subscription import UserSubscription
    from app.models.user import User


class Conversation(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "conversations"

    # ── Foreign Keys ──────────────────────────────────────────────
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    subscription_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("user_subscriptions.id"),
        nullable=True,
    )

    # ── Conversation Identity ─────────────────────────────────────
    title: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(
        String(20), default="active", server_default="active", index=True
    )  # active | closed | timeout | limit_exceeded | archived

    # ── Plan Limits Snapshot (captured at conversation start) ─────
    max_context_messages: Mapped[int] = mapped_column(Integer, nullable=False)
    max_context_tokens: Mapped[int] = mapped_column(Integer, nullable=False)
    conversation_timeout_min: Mapped[int] = mapped_column(Integer, nullable=False)
    memory_retention_days: Mapped[int] = mapped_column(Integer, nullable=False)

    # ── Context Tracking ──────────────────────────────────────────
    total_messages: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0"
    )
    total_tokens_used: Mapped[int] = mapped_column(
        BigInteger, default=0, server_default="0"
    )

    # ── Summary Support ───────────────────────────────────────────
    summary_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    last_summary_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    messages_since_summary: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0"
    )

    # ── Timestamps ────────────────────────────────────────────────
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default="now()", nullable=False
    )
    last_activity_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default="now()", nullable=False, index=True
    )
    closed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    auto_close_reason: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default="now()", nullable=False
    )

    # ── Relationships ─────────────────────────────────────────────
    user: Mapped["User"] = relationship(back_populates="conversations")
    subscription: Mapped[Optional["UserSubscription"]] = relationship(
        back_populates="conversations"
    )
    messages: Mapped[List["Message"]] = relationship(
        back_populates="conversation",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="Message.created_at",
    )

    def __repr__(self) -> str:
        return (
            f"<Conversation(id={self.id}, user={self.user_id}, "
            f"status={self.status}, msgs={self.total_messages})>"
        )

    @property
    def is_active(self) -> bool:
        return self.status == "active"

    @property
    def is_closed(self) -> bool:
        return self.status in ("closed", "timeout", "limit_exceeded", "archived")

    @property
    def needs_summary(self) -> bool:
        """Check if conversation needs auto-summarization based on plan frequency."""
        # This is checked against plan's summary_frequency
        return self.messages_since_summary >= 10  # default, overridden by plan
