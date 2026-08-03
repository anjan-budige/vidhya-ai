"""
Vidhya Bot — Plan Model

Subscription plans with full control layer: message quotas, conversation limits,
context/token controls, memory controls, and feature flags.
"""

import uuid
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import Boolean, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.base import TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.payment import Payment
    from app.models.subscription import UserSubscription


# Default feature flags for new plans
DEFAULT_FEATURES = {
    "rag_enabled": True,
    "streaming_enabled": True,
    "history_export": False,
    "priority_queue": False,
    "subject_filter": False,
    "mcq_mode": False,
}


class Plan(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "plans"

    # ── Identity ──────────────────────────────────────────────────
    name: Mapped[str] = mapped_column(
        String(50), unique=True, nullable=False
    )  # free, basic, premium, pro
    display_name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    price_inr: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0", nullable=False
    )  # price in INR (not paise)
    validity_days: Mapped[int] = mapped_column(
        Integer, default=30, server_default="30", nullable=False
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default="true"
    )

    # ── Message Quotas ────────────────────────────────────────────
    messages_per_day: Mapped[int] = mapped_column(
        Integer, default=5, server_default="5", nullable=False
    )  # -1 = unlimited
    messages_per_month: Mapped[int] = mapped_column(
        Integer, default=50, server_default="50", nullable=False
    )  # -1 = unlimited

    # ── Conversation Limits ───────────────────────────────────────
    max_conversations: Mapped[int] = mapped_column(
        Integer, default=3, server_default="3", nullable=False
    )  # total lifetime
    max_active_conversations: Mapped[int] = mapped_column(
        Integer, default=1, server_default="1", nullable=False
    )  # concurrent open
    conversation_timeout_min: Mapped[int] = mapped_column(
        Integer, default=30, server_default="30", nullable=False
    )  # auto-close after N min idle

    # ── Context / Token Controls ──────────────────────────────────
    max_context_messages: Mapped[int] = mapped_column(
        Integer, default=5, server_default="5", nullable=False
    )  # rolling window size
    max_context_tokens: Mapped[int] = mapped_column(
        Integer, default=2000, server_default="2000", nullable=False
    )  # max tokens sent to LLM
    max_response_tokens: Mapped[int] = mapped_column(
        Integer, default=512, server_default="512", nullable=False
    )  # max tokens in response

    # ── Memory Controls ───────────────────────────────────────────
    memory_retention_days: Mapped[int] = mapped_column(
        Integer, default=7, server_default="7", nullable=False
    )  # how long to keep messages
    summary_frequency: Mapped[int] = mapped_column(
        Integer, default=10, server_default="10", nullable=False
    )  # summarize every N messages
    long_term_memory_enabled: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false"
    )

    # ── Feature Flags ─────────────────────────────────────────────
    features: Mapped[dict] = mapped_column(
        JSONB,
        default=lambda: DEFAULT_FEATURES.copy(),
        server_default='{"rag_enabled": true, "streaming_enabled": true, "history_export": false, "priority_queue": false, "subject_filter": false, "mcq_mode": false}',
    )

    # ── Relationships ─────────────────────────────────────────────
    subscriptions: Mapped[List["UserSubscription"]] = relationship(
        back_populates="plan", lazy="selectin"
    )
    payments: Mapped[List["Payment"]] = relationship(
        back_populates="plan", lazy="selectin"
    )

    def __repr__(self) -> str:
        return f"<Plan(name='{self.name}', price=₹{self.price_inr}, msgs/day={self.messages_per_day})>"

    @property
    def is_free(self) -> bool:
        return self.price_inr == 0

    @property
    def has_unlimited_daily(self) -> bool:
        return self.messages_per_day == -1

    @property
    def has_unlimited_monthly(self) -> bool:
        return self.messages_per_month == -1

    def to_snapshot(self) -> dict:
        """
        Create an immutable snapshot of plan limits.
        Stored in user_subscriptions.plan_snapshot at purchase time.
        """
        return {
            "plan_name": self.name,
            "display_name": self.display_name,
            "price_inr": self.price_inr,
            "messages_per_day": self.messages_per_day,
            "messages_per_month": self.messages_per_month,
            "max_conversations": self.max_conversations,
            "max_active_conversations": self.max_active_conversations,
            "conversation_timeout_min": self.conversation_timeout_min,
            "max_context_messages": self.max_context_messages,
            "max_context_tokens": self.max_context_tokens,
            "max_response_tokens": self.max_response_tokens,
            "memory_retention_days": self.memory_retention_days,
            "summary_frequency": self.summary_frequency,
            "long_term_memory_enabled": self.long_term_memory_enabled,
            "features": self.features,
        }
