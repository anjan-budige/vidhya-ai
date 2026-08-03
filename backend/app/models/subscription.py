"""
Vidhya Bot — User Subscription Model

Links users to plans with immutable plan snapshots and lifetime usage counters.
Enforces one active subscription per user via partial unique index.
"""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import BigInteger, DateTime, Integer, String, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.base import TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.conversation import Conversation
    from app.models.payment import Payment
    from app.models.plan import Plan
    from app.models.usage_tracking import UsageTracking
    from app.models.user import User


class UserSubscription(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "user_subscriptions"

    # ── Foreign Keys ──────────────────────────────────────────────
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    plan_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("plans.id"),
        nullable=False,
    )
    payment_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("payments.id"),
        nullable=True,
    )

    # ── Status ────────────────────────────────────────────────────
    status: Mapped[str] = mapped_column(
        String(20), default="active", server_default="active", index=True
    )  # active | expired | cancelled | paused

    # ── Validity ──────────────────────────────────────────────────
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default="now()", nullable=False
    )
    expires_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # ── Plan Snapshot (immutable after purchase) ──────────────────
    plan_snapshot: Mapped[dict] = mapped_column(JSONB, nullable=False)

    # ── Lifetime Usage Counters ───────────────────────────────────
    total_messages_used: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0"
    )
    total_tokens_consumed: Mapped[int] = mapped_column(
        BigInteger, default=0, server_default="0"
    )
    total_conversations: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0"
    )

    # ── Relationships ─────────────────────────────────────────────
    user: Mapped["User"] = relationship(back_populates="subscriptions")
    plan: Mapped["Plan"] = relationship(back_populates="subscriptions")
    payment: Mapped[Optional["Payment"]] = relationship(
        back_populates="subscription"
    )
    conversations: Mapped[list["Conversation"]] = relationship(
        back_populates="subscription", lazy="selectin"
    )
    usage_records: Mapped[list["UsageTracking"]] = relationship(
        back_populates="subscription", lazy="selectin"
    )

    def __repr__(self) -> str:
        return (
            f"<UserSubscription(id={self.id}, user={self.user_id}, "
            f"status={self.status}, plan={self.plan_snapshot.get('plan_name', '?')})>"
        )

    @property
    def is_active(self) -> bool:
        return self.status == "active"

    @property
    def is_expired(self) -> bool:
        if self.expires_at is None:
            return False
        from datetime import timezone
        return datetime.now(timezone.utc) > self.expires_at

    @property
    def plan_limits(self) -> dict:
        """Access plan limits from the frozen snapshot."""
        return self.plan_snapshot

    @property
    def messages_per_day(self) -> int:
        return self.plan_snapshot.get("messages_per_day", 5)

    @property
    def messages_per_month(self) -> int:
        return self.plan_snapshot.get("messages_per_month", 50)

    @property
    def max_active_conversations(self) -> int:
        return self.plan_snapshot.get("max_active_conversations", 1)

    @property
    def max_context_messages(self) -> int:
        return self.plan_snapshot.get("max_context_messages", 5)

    @property
    def max_context_tokens(self) -> int:
        return self.plan_snapshot.get("max_context_tokens", 2000)

    @property
    def max_response_tokens(self) -> int:
        return self.plan_snapshot.get("max_response_tokens", 512)
