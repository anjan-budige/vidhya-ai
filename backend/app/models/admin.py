"""
Vidhya Bot — Admin Model

Admin accounts with Argon2id password hashing, TOTP 2FA, and brute-force lockout.
"""

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.base import TimestampMixin, UUIDPrimaryKeyMixin


class Admin(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "admins"

    # ── Credentials ───────────────────────────────────────────────
    username: Mapped[str] = mapped_column(
        String(50), unique=True, nullable=False
    )
    email: Mapped[Optional[str]] = mapped_column(
        String(255), unique=True, nullable=True
    )
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)

    # ── Role ──────────────────────────────────────────────────────
    role: Mapped[str] = mapped_column(
        String(20), default="admin", server_default="admin"
    )  # superadmin | admin | viewer

    # ── TOTP (2FA) ────────────────────────────────────────────────
    totp_secret: Mapped[Optional[str]] = mapped_column(
        String(64), nullable=True
    )
    totp_enabled: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false"
    )

    # ── Status ────────────────────────────────────────────────────
    is_active: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default="true"
    )
    failed_login_count: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0"
    )
    locked_until: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_login_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    def __repr__(self) -> str:
        return f"<Admin(id={self.id}, username='{self.username}', role='{self.role}')>"

    @property
    def is_locked(self) -> bool:
        """Check if admin account is currently locked."""
        if self.locked_until is None:
            return False
        from datetime import timezone
        return datetime.now(timezone.utc) < self.locked_until

    @property
    def is_superadmin(self) -> bool:
        return self.role == "superadmin"
