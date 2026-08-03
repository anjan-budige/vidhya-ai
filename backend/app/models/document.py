"""
Vidhya Bot — Document Model

Uploaded PDF metadata with processing status and MinIO storage references.
"""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import BigInteger, Boolean, DateTime, Integer, String, Text, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.base import TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.chunk import DocumentChunk


class Document(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "documents"

    # ── Foreign Keys ──────────────────────────────────────────────
    admin_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("admins.id"),
        nullable=False,
    )

    # ── File Info ─────────────────────────────────────────────────
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    file_size: Mapped[int] = mapped_column(BigInteger, nullable=False)
    mime_type: Mapped[str] = mapped_column(String(100), nullable=False)

    # ── Storage ───────────────────────────────────────────────────
    s3_key: Mapped[str] = mapped_column(String(500), nullable=False)
    s3_bucket: Mapped[str] = mapped_column(String(100), nullable=False)

    # ── Processing Status ─────────────────────────────────────────
    status: Mapped[str] = mapped_column(
        String(20), default="uploaded", server_default="uploaded", index=True
    )  # uploaded | processing | processed | failed
    total_chunks: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0"
    )
    processed_chunks: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0"
    )
    total_pages: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0"
    )
    processing_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    processed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # ── Metadata ──────────────────────────────────────────────────
    subject: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True, index=True
    )
    tags: Mapped[Optional[dict]] = mapped_column(
        JSONB, default=list, server_default="[]"
    )
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # ── Status Flag ───────────────────────────────────────────────
    is_active: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default="true"
    )

    # ── Relationships ─────────────────────────────────────────────
    chunks: Mapped[List["DocumentChunk"]] = relationship(
        back_populates="document",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="DocumentChunk.chunk_index",
    )

    def __repr__(self) -> str:
        return (
            f"<Document(id={self.id}, filename='{self.original_filename}', "
            f"status={self.status}, chunks={self.total_chunks})>"
        )

    @property
    def is_processed(self) -> bool:
        return self.status == "processed"

    @property
    def is_failed(self) -> bool:
        return self.status == "failed"

    @property
    def file_size_mb(self) -> float:
        return round(self.file_size / (1024 * 1024), 2)
