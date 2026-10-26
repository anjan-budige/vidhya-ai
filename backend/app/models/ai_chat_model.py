"""Vidhya AI — chat models (may have several active in future)"""

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.base import TimestampMixin, UUIDPrimaryKeyMixin
from app.services.prompts import DEFAULT_SYSTEM_PROMPT

if TYPE_CHECKING:
    from app.models.ai_provider import AIProvider


class AIChatModel(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "ai_chat_models"
    __table_args__ = (
        UniqueConstraint("provider_id", "name", name="uq_ai_chat_model"),
    )

    provider_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("ai_providers.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    display_name: Mapped[str] = mapped_column(String(160), nullable=False)
    context_window: Mapped[int] = mapped_column(
        Integer, default=32000, server_default="32000", nullable=False
    )
    max_output_tokens: Mapped[int] = mapped_column(
        Integer, default=1024, server_default="1024", nullable=False
    )
    system_prompt: Mapped[str] = mapped_column(
        Text,
        default=DEFAULT_SYSTEM_PROMPT,
        server_default="",
        nullable=False,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default="true", nullable=False
    )
    is_default: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false", nullable=False
    )

    provider: Mapped["AIProvider"] = relationship(back_populates="chat_models")

    def __repr__(self) -> str:
        return f"<AIChatModel(name='{self.name}')>"
