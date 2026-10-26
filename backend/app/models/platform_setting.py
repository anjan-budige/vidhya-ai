"""
Vidhya Bot — Platform Setting Model

Single-row table that controls deployment-wide behaviour.
Currently: whether the platform runs as a paid product or a free platform.
"""

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.base import TimestampMixin


class PlatformSetting(Base, TimestampMixin):
    __tablename__ = "platform_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    platform_mode: Mapped[str] = mapped_column(
        String(10), default="paid", server_default="paid", nullable=False
    )  # "paid" | "free"
    registration_enabled: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false", nullable=False
    )
    email_otp_login: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false", nullable=False
    )
    bot_settings: Mapped[dict] = mapped_column(
        JSONB, default=dict, server_default="{}", nullable=False
    )
    payments_environment: Mapped[str] = mapped_column(
        String(20), default="demo", server_default="demo", nullable=False
    )  # demo | sandbox | production
    default_chat_model_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("ai_chat_models.id", ondelete="SET NULL"),
        nullable=True,
    )

    reindex_status: Mapped[str] = mapped_column(
        String(20), default="idle", server_default="idle", nullable=False
    )  # idle | queued | running | completed | failed
    reindex_target_model_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("ai_embedding_models.id", ondelete="SET NULL"),
        nullable=True,
    )
    reindex_total: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0", nullable=False
    )
    reindex_done: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0", nullable=False
    )
    reindex_failed: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0", nullable=False
    )
    reindex_started_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    reindex_completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    reindex_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    embedding_dimensions: Mapped[int] = mapped_column(
        Integer, default=1024, server_default="1024", nullable=False
    )  # pgvector column width; change requires a migration + re-index
    mode_changed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    mode_changed_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("admins.id", ondelete="SET NULL"),
        nullable=True,
    )

    def __repr__(self) -> str:
        return f"<PlatformSetting(mode='{self.platform_mode}')>"
