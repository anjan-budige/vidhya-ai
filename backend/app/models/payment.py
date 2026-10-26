"""
Vidhya AI — payment providers, orders and webhook events.

Exactly one provider may be active per mode (demo / sandbox / production).
Credentials are stored as a single encrypted JSON blob; see app.utils.crypto.
"""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.base import TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.plan import Plan
    from app.models.subscription import UserSubscription
    from app.models.user import User


class PaymentProvider(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "payment_providers"
    __table_args__ = (
        UniqueConstraint("driver", "mode", name="uq_payment_provider_driver_mode"),
        Index(
            "uq_payment_provider_active",
            "mode",
            unique=True,
            postgresql_where=text("is_active"),
        ),
    )

    driver: Mapped[str] = mapped_column(String(40), nullable=False)
    mode: Mapped[str] = mapped_column(String(20), nullable=False)
    display_name: Mapped[str] = mapped_column(String(120), nullable=False)
    credentials_encrypted: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    config: Mapped[dict] = mapped_column(
        JSONB, default=dict, server_default="{}", nullable=False
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false", nullable=False
    )
    last_tested_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_test_status: Mapped[Optional[str]] = mapped_column(
        String(20), nullable=True
    )
    last_test_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    orders: Mapped[list["PaymentOrder"]] = relationship(
        back_populates="provider"
    )

    def __repr__(self) -> str:
        return f"<PaymentProvider(driver='{self.driver}', mode='{self.mode}')>"


class PaymentOrder(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "payment_orders"
    __table_args__ = (
        UniqueConstraint("user_id", "idempotency_key", name="uq_payment_order_idem"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    plan_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("plans.id", ondelete="SET NULL"),
        nullable=True,
    )
    provider_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("payment_providers.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    provider_driver: Mapped[str] = mapped_column(
        String(40), default="", server_default="", nullable=False
    )
    mode: Mapped[str] = mapped_column(
        String(20), default="sandbox", server_default="sandbox", nullable=False
    )
    is_test: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default="true", nullable=False
    )

    order_ref: Mapped[str] = mapped_column(
        String(64), unique=True, nullable=False, index=True
    )
    idempotency_key: Mapped[Optional[str]] = mapped_column(
        String(128), nullable=True
    )
    provider_order_id: Mapped[Optional[str]] = mapped_column(
        String(191), nullable=True, index=True
    )
    provider_payment_id: Mapped[Optional[str]] = mapped_column(
        String(191), nullable=True
    )

    plan_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    plan_snapshot: Mapped[dict] = mapped_column(
        JSONB, default=dict, server_default="{}", nullable=False
    )
    amount_paise: Mapped[int] = mapped_column(BigInteger, nullable=False)
    currency: Mapped[str] = mapped_column(
        String(3), default="INR", server_default="INR", nullable=False
    )

    status: Mapped[str] = mapped_column(
        String(20), default="created", server_default="created", nullable=False, index=True
    )
    payment_method: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    payment_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    provider_payload: Mapped[dict] = mapped_column(
        JSONB, default=dict, server_default="{}", nullable=False
    )
    failure_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    expires_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    paid_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    user: Mapped["User"] = relationship(back_populates="payment_orders")
    plan: Mapped[Optional["Plan"]] = relationship(back_populates="payment_orders")
    provider: Mapped[Optional["PaymentProvider"]] = relationship(
        back_populates="orders"
    )
    subscription: Mapped[Optional["UserSubscription"]] = relationship(
        back_populates="payment", uselist=False
    )

    @property
    def merchant_txn_id(self) -> str:
        return self.order_ref

    @property
    def amount_inr(self) -> int:
        return self.amount_paise

    @property
    def amount_rupees(self) -> float:
        return self.amount_paise / 100

    @property
    def is_successful(self) -> bool:
        return self.status == "paid"

    def __repr__(self) -> str:
        return (
            f"<PaymentOrder(ref='{self.order_ref}', mode='{self.mode}', "
            f"status='{self.status}', amount={self.amount_paise})>"
        )


class PaymentEvent(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "payment_events"
    __table_args__ = (
        UniqueConstraint("provider_id", "event_id", name="uq_payment_event"),
    )

    provider_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("payment_providers.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    order_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("payment_orders.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    driver: Mapped[str] = mapped_column(String(40), nullable=False)
    mode: Mapped[str] = mapped_column(String(20), nullable=False)
    event_id: Mapped[str] = mapped_column(String(191), nullable=False)
    event_type: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    signature_valid: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false", nullable=False
    )
    payload_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), default="received", server_default="received", nullable=False
    )
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default="now()", nullable=False
    )

    def __repr__(self) -> str:
        return f"<PaymentEvent(event='{self.event_id}', status='{self.status}')>"
