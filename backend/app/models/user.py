"""
Vidhya Bot — User Model

Accounts can originate from Telegram, public web registration, or an admin.
Only `first_name` is required; every identifier is optional so a Telegram user
and a web user can coexist in the same table.
"""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import BigInteger, Boolean, DateTime, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.base import TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.conversation import Conversation
    from app.models.message import Message
    from app.models.payment import PaymentOrder
    from app.models.session import Session
    from app.models.subscription import UserSubscription
    from app.models.usage_tracking import UsageTracking
    from app.models.user_api_key import UserApiKey


class User(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "users"

    telegram_id: Mapped[Optional[int]] = mapped_column(
        BigInteger, unique=True, nullable=True, index=True
    )
    telegram_username: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True
    )
    username: Mapped[Optional[str]] = mapped_column(
        String(30), unique=True, nullable=True, index=True
    )
    email: Mapped[Optional[str]] = mapped_column(
        String(255), unique=True, nullable=True, index=True
    )
    mobile: Mapped[Optional[str]] = mapped_column(
        String(20), unique=True, nullable=True, index=True
    )

    password_hash: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    auth_provider: Mapped[str] = mapped_column(
        String(20), default="telegram", server_default="telegram", nullable=False
    )  # telegram | web | admin
    email_verified_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    last_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    photo_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    language_code: Mapped[str] = mapped_column(
        String(10), default="en", server_default="en"
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default="true"
    )
    is_banned: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false"
    )
    ban_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    last_login_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    sessions: Mapped[List["Session"]] = relationship(
        back_populates="user", cascade="all, delete-orphan", lazy="selectin"
    )
    subscriptions: Mapped[List["UserSubscription"]] = relationship(
        back_populates="user", cascade="all, delete-orphan", lazy="selectin"
    )
    payment_orders: Mapped[List["PaymentOrder"]] = relationship(
        back_populates="user", cascade="all, delete-orphan", lazy="selectin"
    )
    conversations: Mapped[List["Conversation"]] = relationship(
        back_populates="user", cascade="all, delete-orphan", lazy="selectin"
    )
    messages: Mapped[List["Message"]] = relationship(
        back_populates="user", cascade="all, delete-orphan", lazy="selectin"
    )
    usage_records: Mapped[List["UsageTracking"]] = relationship(
        back_populates="user", cascade="all, delete-orphan", lazy="selectin"
    )
    api_keys: Mapped[List["UserApiKey"]] = relationship(
        back_populates="user", cascade="all, delete-orphan", lazy="selectin"
    )

    def __repr__(self) -> str:
        ident = self.username or self.telegram_id or self.email or "?"
        return f"<User(id={self.id}, ident={ident}, name='{self.first_name}')>"
