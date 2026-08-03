"""Vidhya Bot — Document Schemas"""

import uuid
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field

from app.schemas.base import VidhyaBaseModel


class DocumentUploadResponse(VidhyaBaseModel):
    """Response after uploading a document."""
    id: uuid.UUID
    filename: str
    original_filename: str
    file_size: int
    mime_type: str
    status: str
    created_at: datetime


class DocumentResponse(VidhyaBaseModel):
    """Full document details."""
    id: uuid.UUID
    filename: str
    original_filename: str
    file_size: int
    mime_type: str
    s3_key: str
    s3_bucket: str
    status: str
    total_chunks: int = 0
    processed_chunks: int = 0
    total_pages: int = 0
    processing_error: Optional[str] = None
    processed_at: Optional[datetime] = None
    subject: Optional[str] = None
    tags: Optional[list] = None
    description: Optional[str] = None
    is_active: bool
    created_at: datetime
    updated_at: datetime


class DocumentUpdateRequest(BaseModel):
    """Update document metadata."""
    subject: Optional[str] = Field(None, max_length=100)
    description: Optional[str] = None
    tags: Optional[list] = None
    is_active: Optional[bool] = None


class DocumentListResponse(VidhyaBaseModel):
    """Document in list view."""
    id: uuid.UUID
    original_filename: str
    file_size: int
    status: str
    total_chunks: int = 0
    processed_chunks: int = 0
    total_pages: int = 0
    subject: Optional[str] = None
    is_active: bool
    created_at: datetime


class ChunkResponse(VidhyaBaseModel):
    """Document chunk details."""
    id: uuid.UUID
    document_id: uuid.UUID
    chunk_index: int
    content: str
    token_count: int = 0
    page_number: Optional[int] = None
    section_title: Optional[str] = None
    metadata: Optional[dict] = None
    created_at: datetime
