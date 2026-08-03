"""
Vidhya Bot — Document Chunk Model

Chunked text from PDFs with 768-dimensional vector embeddings (nomic-embed-text)
for RAG similarity search via pgvector HNSW index.
"""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from pgvector.sqlalchemy import Vector
from sqlalchemy import DateTime, Integer, String, Text, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.base import UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.document import Document

from app.config import get_settings

settings = get_settings()

# Dimension comes from config (1024 for Mistral, 1536 for OpenAI, 768 for Nomic)
EMBEDDING_DIMENSIONS = settings.EMBEDDING_DIMENSIONS


class DocumentChunk(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "document_chunks"

    # ── Foreign Keys ──────────────────────────────────────────────
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # ── Chunk Content ─────────────────────────────────────────────
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    token_count: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0"
    )

    # ── Embedding (768d — nomic-embed-text) ───────────────────────
    embedding = mapped_column(
        Vector(EMBEDDING_DIMENSIONS), nullable=True
    )

    # ── Metadata ──────────────────────────────────────────────────
    page_number: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    section_title: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True
    )
    chunk_metadata: Mapped[Optional[dict]] = mapped_column(
        "metadata", JSONB, default=dict, server_default="{}"
    )

    # ── Timestamps ────────────────────────────────────────────────
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default="now()", nullable=False
    )

    # ── Relationships ─────────────────────────────────────────────
    document: Mapped["Document"] = relationship(back_populates="chunks")

    def __repr__(self) -> str:
        content_preview = self.content[:60] + "..." if len(self.content) > 60 else self.content
        return (
            f"<DocumentChunk(doc={self.document_id}, idx={self.chunk_index}, "
            f"tokens={self.token_count}, content='{content_preview}')>"
        )
