"""
Vidhya Bot — Usage Tracking Model

Per-day and per-month usage counters for quota enforcement.
Synced from Redis to DB by Celery tasks.
"""

import uuid
from datetime import date, datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import BigInteger, Date, Integer, String, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.base import TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.subscription import UserSubscription
    from app.models.user import User


class UsageTracking(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "usage_tracking"
    __table_args__ = (
        UniqueConstraint("user_id", "period_type", "period_date", name="uq_usage_user_period"),
    )

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

    # ── Period ────────────────────────────────────────────────────
    period_type: Mapped[str] = mapped_column(
        String(10), nullable=False
    )  # 'daily' | 'monthly'
    period_date: Mapped[date] = mapped_column(
        Date, nullable=False
    )  # e.g. 2024-05-28 or 2024-05-01

    # ── Counters ──────────────────────────────────────────────────
    messages_used: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0"
    )
    tokens_input: Mapped[int] = mapped_column(
        BigInteger, default=0, server_default="0"
    )
    tokens_output: Mapped[int] = mapped_column(
        BigInteger, default=0, server_default="0"
    )
    conversations_created: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0"
    )

    # ── Relationships ─────────────────────────────────────────────
    user: Mapped["User"] = relationship(back_populates="usage_records")
    subscription: Mapped[Optional["UserSubscription"]] = relationship(
        back_populates="usage_records"
    )

    def __repr__(self) -> str:
        return (
            f"<UsageTracking(user={self.user_id}, {self.period_type}={self.period_date}, "
            f"msgs={self.messages_used})>"
        )

    @property
    def total_tokens(self) -> int:
        return self.tokens_input + self.tokens_output
