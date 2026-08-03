"""
Vidhya Bot — Audit Log Model

Immutable audit trail for all admin actions — plan changes,
user management, document operations, and system events.
"""

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, String, Text, ForeignKey
from sqlalchemy.dialects.postgresql import INET, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.base import UUIDPrimaryKeyMixin


class AuditLog(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "audit_logs"

    # ── Who ───────────────────────────────────────────────────────
    admin_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("admins.id"),
        nullable=True,
        index=True,
    )

    # ── What ──────────────────────────────────────────────────────
    action: Mapped[str] = mapped_column(
        String(100), nullable=False, index=True
    )  # e.g. "plan.created", "user.banned", "document.uploaded"
    resource_type: Mapped[Optional[str]] = mapped_column(
        String(50), nullable=True
    )  # user, plan, document, subscription, etc.
    resource_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    details: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    # ── Context ───────────────────────────────────────────────────
    ip_address: Mapped[Optional[str]] = mapped_column(INET, nullable=True)
    user_agent: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # ── Timestamp (immutable — no updated_at) ─────────────────────
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default="now()", nullable=False, index=True
    )

    def __repr__(self) -> str:
        return (
            f"<AuditLog(action='{self.action}', resource={self.resource_type}:{self.resource_id}, "
            f"admin={self.admin_id})>"
        )
