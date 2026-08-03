"""
Vidhya Bot — Payment Model

PhonePe payment records with transaction tracking and status management.
"""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import DateTime, Float, Integer, String, Text, Boolean
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import ForeignKey

from app.database import Base
from app.models.base import TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.plan import Plan
    from app.models.user import User
    from app.models.subscription import UserSubscription


class Payment(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "payments"

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

    # ── PhonePe Transaction ───────────────────────────────────────
    merchant_txn_id: Mapped[str] = mapped_column(
        String(100), unique=True, nullable=False, index=True
    )
    phonepe_txn_id: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True
    )
    amount_inr: Mapped[int] = mapped_column(
        Integer, nullable=False
    )  # Amount in PAISE (₹99 = 9900)
    currency: Mapped[str] = mapped_column(
        String(10), default="INR", server_default="INR"
    )

    # ── Status ────────────────────────────────────────────────────
    status: Mapped[str] = mapped_column(
        String(20), default="initiated", server_default="initiated", index=True
    )  # initiated | pending | success | failed | refunded

    # ── Payment Details ───────────────────────────────────────────
    payment_method: Mapped[Optional[str]] = mapped_column(
        String(50), nullable=True
    )  # UPI, CARD, NETBANKING, etc.
    payment_instrument: Mapped[Optional[dict]] = mapped_column(
        JSONB, nullable=True
    )  # instrument details from PhonePe
    response_data: Mapped[Optional[dict]] = mapped_column(
        JSONB, nullable=True
    )  # full PhonePe response for debugging

    # ── Timestamps ────────────────────────────────────────────────
    initiated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default="now()", nullable=False
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # ── Relationships ─────────────────────────────────────────────
    user: Mapped["User"] = relationship(back_populates="payments")
    plan: Mapped["Plan"] = relationship(back_populates="payments")
    subscription: Mapped[Optional["UserSubscription"]] = relationship(
        back_populates="payment", uselist=False
    )

    def __repr__(self) -> str:
        return f"<Payment(id={self.id}, txn={self.merchant_txn_id}, status={self.status}, amount={self.amount_inr})>"

    @property
    def amount_rupees(self) -> float:
        """Convert paise to rupees."""
        return self.amount_inr / 100

    @property
    def is_successful(self) -> bool:
        return self.status == "success"
