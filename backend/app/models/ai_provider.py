"""Vidhya AI — AI provider configuration"""

import uuid
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import Boolean, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.base import TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.ai_chat_model import AIChatModel
    from app.models.ai_embedding_model import AIEmbeddingModel


class AIProvider(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "ai_providers"

    name: Mapped[str] = mapped_column(String(80), unique=True, nullable=False, index=True)
    adapter: Mapped[str] = mapped_column(
        String(30), default="openai_compatible", server_default="openai_compatible"
    )
    base_url: Mapped[str] = mapped_column(Text, nullable=False)
    # Optional full endpoint overrides for the "custom" adapter.
    chat_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    embeddings_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    models_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    auth_type: Mapped[str] = mapped_column(
        String(20), default="bearer", server_default="bearer"
    )  # bearer | header | query | basic | none
    auth_key_name: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    auth_username: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    api_key_encrypted: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default="true", nullable=False
    )
    created_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("admins.id", ondelete="SET NULL"),
        nullable=True,
    )

    chat_models: Mapped[List["AIChatModel"]] = relationship(
        back_populates="provider", cascade="all, delete-orphan", lazy="selectin"
    )
    embedding_models: Mapped[List["AIEmbeddingModel"]] = relationship(
        back_populates="provider", cascade="all, delete-orphan", lazy="selectin"
    )

    def __repr__(self) -> str:
        return f"<AIProvider(name='{self.name}', adapter='{self.adapter}')>"
