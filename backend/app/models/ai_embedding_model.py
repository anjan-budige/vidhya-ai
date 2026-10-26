"""Vidhya AI — embedding models (exactly one active globally)"""

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.base import TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.ai_provider import AIProvider


class AIEmbeddingModel(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "ai_embedding_models"
    __table_args__ = (
        UniqueConstraint("provider_id", "name", name="uq_ai_embedding_model"),
    )

    provider_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("ai_providers.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    display_name: Mapped[str] = mapped_column(String(160), nullable=False)
    embedding_dimensions: Mapped[int] = mapped_column(Integer, nullable=False)
    is_active: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false", nullable=False
    )

    provider: Mapped["AIProvider"] = relationship(back_populates="embedding_models")

    def __repr__(self) -> str:
        return f"<AIEmbeddingModel(name='{self.name}')>"
