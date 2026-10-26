"""Vidhya Bot — Plan Schemas"""

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

from app.schemas.base import VidhyaBaseModel



class PlanFeatures(BaseModel):
    """Plan feature flags."""
    rag_enabled: bool = True
    streaming_enabled: bool = True
    history_export: bool = False
    priority_queue: bool = False
    subject_filter: bool = False
    mcq_mode: bool = False



class PlanCreateRequest(BaseModel):
    """Create a new plan (admin only)."""
    name: str = Field(..., min_length=2, max_length=50, pattern=r"^[a-z_]+$")
    display_name: str = Field(..., min_length=2, max_length=100)
    description: Optional[str] = None
    price_inr: int = Field(default=0, ge=0)
    validity_days: int = Field(default=30, ge=1)

    messages_per_day: int = Field(default=5, ge=-1)
    messages_per_month: int = Field(default=50, ge=-1)

    max_sessions: int = Field(default=5, ge=-1)

    max_context_tokens: int = Field(default=2000, ge=500)
    max_response_tokens: int = Field(default=512, ge=128)

    memory_retention_days: int = Field(default=7, ge=1)
    summary_frequency: int = Field(default=10, ge=5)
    long_term_memory_enabled: bool = False

    features: PlanFeatures = Field(default_factory=PlanFeatures)


class PlanUpdateRequest(BaseModel):
    """Update plan fields (admin only)."""
    display_name: Optional[str] = Field(None, min_length=2, max_length=100)
    description: Optional[str] = None
    price_inr: Optional[int] = Field(None, ge=0)
    validity_days: Optional[int] = Field(None, ge=1)
    is_active: Optional[bool] = None

    messages_per_day: Optional[int] = Field(None, ge=-1)
    messages_per_month: Optional[int] = Field(None, ge=-1)

    max_sessions: Optional[int] = Field(None, ge=-1)

    max_context_tokens: Optional[int] = Field(None, ge=500)
    max_response_tokens: Optional[int] = Field(None, ge=128)

    memory_retention_days: Optional[int] = Field(None, ge=1)
    summary_frequency: Optional[int] = Field(None, ge=5)
    long_term_memory_enabled: Optional[bool] = None

    features: Optional[PlanFeatures] = None


class PlanResponse(VidhyaBaseModel):
    """Plan details response."""
    id: uuid.UUID
    name: str
    display_name: str
    description: Optional[str] = None
    price_inr: int
    validity_days: int
    is_active: bool

    messages_per_day: int
    messages_per_month: int

    max_sessions: int

    max_context_tokens: int
    max_response_tokens: int

    memory_retention_days: int
    summary_frequency: int
    long_term_memory_enabled: bool

    features: dict

    created_at: datetime
    updated_at: datetime


class PlanPublicResponse(VidhyaBaseModel):
    """Plan info shown to users (no internal details)."""
    id: uuid.UUID
    name: str
    display_name: str
    description: Optional[str] = None
    price_inr: int
    validity_days: int

    messages_per_day: int
    messages_per_month: int
    max_sessions: int

    max_context_tokens: int
    max_response_tokens: int

    features: dict
