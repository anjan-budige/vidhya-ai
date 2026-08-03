"""
╔══════════════════════════════════════════════════════════════════╗
║  VIDHYA BOT — Documents Router                                   ║
║  Provides: Multipart S3 uploads, metadata updating, list queries ║
║  and deletion cascade cleanups.                                  ║
╚══════════════════════════════════════════════════════════════════╝
"""

import uuid
from datetime import datetime, timezone
from typing import List, Optional

import boto3
import magic
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, status
from sqlalchemy import select, delete, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import (
    get_db,
    get_current_admin,
    get_pagination
)
from app.config import get_settings
from app.models.document import Document
from app.models.chunk import DocumentChunk
from app.models.audit_log import AuditLog
from app.schemas.document import (
    DocumentUploadResponse,
    DocumentResponse,
    DocumentUpdateRequest,
    DocumentListResponse,
    ChunkResponse
)
from app.schemas.auth import CurrentAdmin
from app.schemas.base import PaginationParams

settings = get_settings()

router = APIRouter(prefix="/documents", tags=["Admin Document Ingestion"])

from botocore.config import Config

# Initialize thread-safe boto3 s3 client singleton
s3_client = boto3.client(
    "s3",
    endpoint_url=settings.MINIO_ENDPOINT,
    aws_access_key_id=settings.MINIO_ROOT_USER,
    aws_secret_access_key=settings.MINIO_ROOT_PASSWORD,
    region_name=settings.MINIO_REGION,
    config=Config(s3={'addressing_style': 'path'}, signature_version='s3v4')
)


@router.post("/upload", response_model=DocumentUploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_pdf_document(
    file: UploadFile = File(..., description="PDF document upload"),
    subject: Optional[str] = Form(None, description="Topic subject classification"),
    description: Optional[str] = Form(None, description="File description"),
    tags: Optional[str] = Form(None, description="Comma separated tags"),
    current_admin: CurrentAdmin = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    Ingest a PDF document (Admin only).
    Stores raw files in MinIO and registers the record in PostgreSQL to trigger Celery indexing.
    """
    # 1. Validate file format and size
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid file format. Only PDF documents are allowed."
        )
        
    # Read bytes to verify file limits
    file_bytes = await file.read()
    file_size = len(file_bytes)
    
    if file_size > settings.max_upload_size_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File exceeds maximum allowed size ({settings.MAX_UPLOAD_SIZE_MB}MB)."
        )
        
    # 1.5 Deep MIME Magic Byte validation
    detected_mime = magic.from_buffer(file_bytes[:2048], mime=True)
    if detected_mime != "application/pdf":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Security violation: File is not a valid PDF. Detected type: {detected_mime}"
        )
        
    # 2. Build S3 target Key
    doc_uuid = uuid.uuid4()
    original_filename = file.filename
    sanitized_filename = "".join(c for c in original_filename if c.isalnum() or c in (".", "-", "_")).strip()
    
    subject_folder = subject.strip().lower() if subject else "uncategorized"
    s3_key = f"subjects/{subject_folder}/{doc_uuid}-{sanitized_filename}"
    
    # 3. Upload file stream directly to MinIO
    try:
        s3_client.put_object(
            Bucket=settings.MINIO_BUCKET,
            Key=s3_key,
            Body=file_bytes,
            ContentType="application/pdf"
        )
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"S3 Object Storage upload failed: {str(e)}"
        )
        
    # 4. Insert Document record in Database
    doc = Document(
        id=doc_uuid,
        admin_id=current_admin.id,
        filename=f"{doc_uuid}-{sanitized_filename}",
        original_filename=original_filename,
        file_size=file_size,
        mime_type="application/pdf",
        s3_key=s3_key,
        s3_bucket=settings.MINIO_BUCKET,
        status="uploaded",
        total_chunks=0,
        total_pages=0,
        subject=subject,
        description=description,
        tags=[t.strip() for t in tags.split(",")] if tags else [],
        is_active=True,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc)
    )
    db.add(doc)
    await db.flush()
    
    # Audit Logging
    db.add(AuditLog(
        admin_id=current_admin.id,
        action="document.uploaded",
        resource_type="document",
        resource_id=doc.id,
        details={"filename": original_filename, "subject": subject}
    ))
    
    await db.commit()
    
    # 5. Trigger asynchronous Celery parsing task
    try:
        from celery import Celery
        celery_client = Celery("vidhya")
        celery_client.send_task(
            "vidhya.ingest_pdf",
            args=[str(doc.id)],
            queue="pdf"
        )
    except Exception:
        pass  # Worker tasks offline, will run when beat/worker triggers in worker phase
        
    return DocumentUploadResponse(
        id=doc.id,
        filename=doc.filename,
        original_filename=doc.original_filename,
        file_size=doc.file_size,
        mime_type=doc.mime_type,
        status=doc.status,
        created_at=doc.created_at
    )


@router.get("/", response_model=List[DocumentListResponse], status_code=status.HTTP_200_OK)
async def list_ingested_documents(
    current_admin: CurrentAdmin = Depends(get_current_admin),
    pagination: PaginationParams = Depends(get_pagination),
    db: AsyncSession = Depends(get_db)
):
    """
    List paginated document records (Admin only).
    """
    offset = (pagination.page - 1) * pagination.page_size
    stmt = (
        select(Document)
        .order_by(desc(Document.created_at))
        .offset(offset)
        .limit(pagination.page_size)
    )
    result = await db.execute(stmt)
    documents = result.scalars().all()
    return documents


@router.get("/{doc_id}", response_model=DocumentResponse, status_code=status.HTTP_200_OK)
async def get_document_details(
    doc_id: uuid.UUID,
    current_admin: CurrentAdmin = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    Retrieve metadata of a specific document (Admin only).
    """
    result = await db.execute(select(Document).where(Document.id == doc_id))
    doc = result.scalar_one_or_none()
    
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found."
        )
    return doc


from fastapi.responses import StreamingResponse

@router.get("/{doc_id}/download", status_code=status.HTTP_200_OK)
async def download_document(
    doc_id: uuid.UUID,
    current_admin: CurrentAdmin = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    Securely download the raw PDF document from MinIO (Admin only).
    """
    result = await db.execute(select(Document).where(Document.id == doc_id))
    doc = result.scalar_one_or_none()
    
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found."
        )
        
    try:
        s3_response = s3_client.get_object(Bucket=doc.s3_bucket, Key=doc.s3_key)
        
        # Audit Logging
        db.add(AuditLog(
            admin_id=current_admin.id,
            action="document.downloaded",
            resource_type="document",
            resource_id=doc.id,
            details={"filename": doc.original_filename}
        ))
        await db.commit()
        
        return StreamingResponse(
            s3_response["Body"],
            media_type=doc.mime_type or "application/pdf",
            headers={"Content-Disposition": f'attachment; filename="{doc.original_filename}"'}
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch document from storage: {str(e)}"
        )


@router.put("/{doc_id}", response_model=DocumentResponse, status_code=status.HTTP_200_OK)
async def update_document_metadata(
    doc_id: uuid.UUID,
    payload: DocumentUpdateRequest,
    current_admin: CurrentAdmin = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    Update document subject classifications, description, active flags, or tags (Admin only).
    """
    result = await db.execute(select(Document).where(Document.id == doc_id))
    doc = result.scalar_one_or_none()
    
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found."
        )
        
    update_data = payload.model_dump(exclude_unset=True)
    for key, val in update_data.items():
        setattr(doc, key, val)
        
    doc.updated_at = datetime.now(timezone.utc)
    
    # Audit Logging
    db.add(AuditLog(
        admin_id=current_admin.id,
        action="document.updated",
        resource_type="document",
        resource_id=doc.id,
        details={"updates": list(update_data.keys())}
    ))
    
    await db.commit()
    await db.refresh(doc)
    return doc


@router.get("/{doc_id}/chunks", response_model=List[ChunkResponse], status_code=status.HTTP_200_OK)
async def get_document_parsed_chunks(
    doc_id: uuid.UUID,
    current_admin: CurrentAdmin = Depends(get_current_admin),
    pagination: PaginationParams = Depends(get_pagination),
    db: AsyncSession = Depends(get_db)
):
    """
    Retrieve paginated vector embedding text chunks associated with the document (Admin only).
    """
    # Verify document exists
    result = await db.execute(select(Document).where(Document.id == doc_id))
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found.")
        
    offset = (pagination.page - 1) * pagination.page_size
    stmt = (
        select(DocumentChunk)
        .where(DocumentChunk.document_id == doc_id)
        .order_by(DocumentChunk.chunk_index.asc())
        .offset(offset)
        .limit(pagination.page_size)
    )
    res_chunks = await db.execute(stmt)
    chunks = res_chunks.scalars().all()
    return chunks


@router.delete("/{doc_id}", status_code=status.HTTP_200_OK)
async def delete_document(
    doc_id: uuid.UUID,
    current_admin: CurrentAdmin = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    Delete a document completely (Admin only).
    Evicts the file from S3 and cascade-deletes all associated pgvector DocumentChunks.
    """
    result = await db.execute(select(Document).where(Document.id == doc_id))
    doc = result.scalar_one_or_none()
    
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found."
        )
        
    # 1. Evict file from MinIO
    try:
        s3_client.delete_object(
            Bucket=doc.s3_bucket,
            Key=doc.s3_key
        )
    except Exception as e:
        # Log error, proceed to delete DB record anyway to ensure DB cleanup
        pass
        
    # 2. Delete dependent DocumentChunks manually for safety
    from app.models.chunk import DocumentChunk
    await db.execute(delete(DocumentChunk).where(DocumentChunk.document_id == doc_id))
    
    # 3. Delete Document from DB
    await db.execute(delete(Document).where(Document.id == doc_id))
    
    # Audit Logging
    db.add(AuditLog(
        admin_id=current_admin.id,
        action="document.deleted",
        resource_type="document",
        resource_id=doc_id,
        details={"filename": doc.original_filename}
    ))
    
    await db.commit()
    
    return {"detail": f"Document '{doc.original_filename}' and associated chunks deleted successfully."}
