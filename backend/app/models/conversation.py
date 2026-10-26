"""
Vidhya Bot — Conversation Model

A saved chat session with plan-bound context limits and
auto-summarization support. Sessions have no active/closed state.
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

    title: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    max_context_tokens: Mapped[int] = mapped_column(Integer, nullable=False)
    memory_retention_days: Mapped[int] = mapped_column(Integer, nullable=False)

    total_messages: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0"
    )
    total_tokens_used: Mapped[int] = mapped_column(
        BigInteger, default=0, server_default="0"
    )

    summary_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    last_summary_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    messages_since_summary: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0"
    )

    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default="now()", nullable=False
    )
    last_activity_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default="now()", nullable=False, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default="now()", nullable=False
    )

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
            f"msgs={self.total_messages})>"
        )

    @property
    def needs_summary(self) -> bool:
        """Check if conversation needs auto-summarization based on plan frequency."""
        # This is checked against plan's summary_frequency
        return self.messages_since_summary >= 10  # default, overridden by plan
