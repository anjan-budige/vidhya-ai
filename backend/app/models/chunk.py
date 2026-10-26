"""
Vidhya Bot — Document Chunk Model

Chunked text from PDFs with vector embeddings from the active embedding model,
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


class DocumentChunk(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "document_chunks"

    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    token_count: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0"
    )

    # The column dimension is defined in the database schema (vector(1024)).
    embedding = mapped_column(Vector(), nullable=True)
    embedding_model_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("ai_embedding_models.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    page_number: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    section_title: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True
    )
    chunk_metadata: Mapped[Optional[dict]] = mapped_column(
        "metadata", JSONB, default=dict, server_default="{}"
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default="now()", nullable=False
    )

    document: Mapped["Document"] = relationship(back_populates="chunks")

    def __repr__(self) -> str:
        content_preview = self.content[:60] + "..." if len(self.content) > 60 else self.content
        return (
            f"<DocumentChunk(doc={self.document_id}, idx={self.chunk_index}, "
            f"tokens={self.token_count}, content='{content_preview}')>"
        )
