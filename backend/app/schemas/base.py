"""
Vidhya Bot — Base Schemas

Common Pydantic models used across the application.
"""

import uuid
from datetime import datetime
from typing import Any, Generic, List, Optional, TypeVar

from pydantic import BaseModel, ConfigDict, Field


# ═══════════════════════════════════════════════════════════════════
# Base Response Models
# ═══════════════════════════════════════════════════════════════════

class VidhyaBaseModel(BaseModel):
    """Base model with ORM mode enabled."""
    model_config = ConfigDict(from_attributes=True)


class HealthResponse(BaseModel):
    status: str
    service: str
    version: str
    timestamp: datetime


class DetailedHealthResponse(HealthResponse):
    environment: str
    uptime_seconds: float
    services: dict


# ═══════════════════════════════════════════════════════════════════
# Pagination
# ═══════════════════════════════════════════════════════════════════

T = TypeVar("T")


class PaginatedResponse(BaseModel, Generic[T]):
    """Standard paginated response wrapper."""
    items: List[T]
    total: int
    page: int = 1
    page_size: int = 20
    total_pages: int = 1

    @classmethod
    def create(cls, items: List[T], total: int, page: int, page_size: int):
        total_pages = max(1, (total + page_size - 1) // page_size)
        return cls(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
        )


class PaginationParams(BaseModel):
    """Query params for pagination."""
    page: int = Field(default=1, ge=1, description="Page number")
    page_size: int = Field(default=20, ge=1, le=100, description="Items per page")

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.page_size


# ═══════════════════════════════════════════════════════════════════
# Error Responses
# ═══════════════════════════════════════════════════════════════════

class ErrorResponse(BaseModel):
    """Standard error response."""
    error: str
    message: str
    details: Optional[dict] = None


class QuotaExceededResponse(ErrorResponse):
    """Quota exceeded error with upgrade CTA."""
    quota: Optional[dict] = None
    upgrade_url: str = "http://localhost/plans"


class SubscriptionRequiredResponse(ErrorResponse):
    """Subscription required error."""
    upgrade_url: str = "http://localhost/plans"


# ═══════════════════════════════════════════════════════════════════
# Success Response
# ═══════════════════════════════════════════════════════════════════

class SuccessResponse(BaseModel):
    """Generic success response."""
    success: bool = True
    message: str = "Operation completed successfully"
    data: Optional[Any] = None


class DeleteResponse(BaseModel):
    """Response after deletion."""
    success: bool = True
    message: str = "Resource deleted successfully"
    id: uuid.UUID
