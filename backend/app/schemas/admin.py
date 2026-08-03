"""Vidhya Bot — Admin Schemas"""

import uuid
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field

from app.schemas.base import VidhyaBaseModel


class AdminCreateRequest(BaseModel):
    """Create a new admin (superadmin only)."""
    username: str = Field(..., min_length=3, max_length=50)
    email: Optional[str] = Field(None, max_length=255)
    password: str = Field(..., min_length=8, max_length=128)
    role: str = Field(default="admin", pattern=r"^(superadmin|admin|viewer)$")
    totp_enabled: bool = False


class AdminResponse(VidhyaBaseModel):
    """Admin profile response."""
    id: uuid.UUID
    username: str
    email: Optional[str]
    role: str
    totp_enabled: bool
    is_active: bool
    failed_login_count: int = 0
    locked_until: Optional[datetime] = None
    last_login_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime


class AdminUpdateRequest(BaseModel):
    """Update admin fields."""
    email: Optional[str] = Field(None, max_length=255)
    role: Optional[str] = Field(None, pattern=r"^(superadmin|admin|viewer)$")
    is_active: Optional[bool] = None
    totp_enabled: Optional[bool] = None


class AuditLogResponse(VidhyaBaseModel):
    """Audit log entry."""
    id: uuid.UUID
    admin_id: Optional[uuid.UUID] = None
    admin_username: Optional[str] = None
    action: str
    resource_type: Optional[str] = None
    resource_id: Optional[uuid.UUID] = None
    details: Optional[dict] = None
    ip_address: Optional[str] = None
    created_at: datetime

class PaginatedAuditLogResponse(VidhyaBaseModel):
    """Paginated audit log list."""
    items: List[AuditLogResponse]
    total: int
    page: int
    page_size: int
