import re
import uuid
from datetime import datetime, timezone
from typing import List, Optional
from urllib.parse import quote

import boto3
import magic
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, status
from sqlalchemy import select, delete, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import (
    get_db,
    get_current_admin,
    get_pagination,
    require_admin_or_above,
    require_superadmin,
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

# Extension -> canonical type used for storage and for choosing the extractor.
UPLOAD_TYPES = {
    ".pdf": "application/pdf",
    ".txt": "text/plain",
    ".md": "text/markdown",
    ".markdown": "text/markdown",
    ".csv": "text/csv",
    ".json": "application/json",
    ".log": "text/plain",
}
TEXT_EXTENSIONS = {ext for ext, mime in UPLOAD_TYPES.items() if mime != "application/pdf"}


def _is_text_payload(data: bytes) -> bool:
    """Reject binary masquerading as text: no NUL bytes, few control chars."""
    sample = data[:65536]
    if b"\x00" in sample:
        return False
    control = sum(1 for b in sample if b < 9 or 13 < b < 32)
    return control / max(1, len(sample)) < 0.05


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
    file: UploadFile = File(..., description="PDF or plain-text document"),
    subject: Optional[str] = Form(None, description="Topic subject classification"),
    description: Optional[str] = Form(None, description="File description"),
    tags: Optional[str] = Form(None, description="Comma separated tags"),
    current_admin: CurrentAdmin = Depends(require_admin_or_above),
    db: AsyncSession = Depends(get_db)
):
    """
    Ingest a document (Admin only): PDF pages or a plain-text file.
    Stores raw files in MinIO and registers the record in PostgreSQL to trigger Celery indexing.
    """
    # 1. Validate file format and size
    extension = ("." + file.filename.rsplit(".", 1)[-1].lower()) if "." in file.filename else ""
    if extension not in UPLOAD_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Unsupported file type. Allowed: "
                + ", ".join(sorted(UPLOAD_TYPES))
            )
        )
    content_type = UPLOAD_TYPES[extension]

    file_bytes = await file.read()
    file_size = len(file_bytes)

    if not file_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The uploaded file is empty."
        )

    if file_size > settings.max_upload_size_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File exceeds maximum allowed size ({settings.MAX_UPLOAD_SIZE_MB}MB)."
        )
        
    # 1.5 Deep MIME Magic Byte validation
    detected_mime = magic.from_buffer(file_bytes[:2048], mime=True)
    if content_type == "application/pdf":
        if detected_mime != "application/pdf":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Security violation: File is not a valid PDF. Detected type: {detected_mime}"
            )
    elif extension in TEXT_EXTENSIONS:
        if not _is_text_payload(file_bytes):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Security violation: File is not plain text."
            )
        if detected_mime not in content_type and not detected_mime.startswith("text/"):
            if detected_mime not in ("application/json", "application/octet-stream", "inode/x-empty"):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Security violation: Unexpected content type {detected_mime}."
                )
        
    # 2. Build S3 target Key
    doc_uuid = uuid.uuid4()
    original_filename = file.filename
    sanitized_filename = "".join(c for c in original_filename if c.isalnum() or c in (".", "-", "_")).strip()
    
    subject_folder = (
        re.sub(r"[^a-z0-9_-]+", "-", (subject or "").strip().lower()).strip("-")
        or "uncategorized"
    )
    s3_key = f"subjects/{subject_folder}/{doc_uuid}-{sanitized_filename or f'document{extension}'}"
    
    # 3. Upload file stream directly to MinIO
    try:
        s3_client.put_object(
            Bucket=settings.MINIO_BUCKET,
            Key=s3_key,
            Body=file_bytes,
            ContentType=content_type
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
        mime_type=content_type,
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
        
        db.add(AuditLog(
            admin_id=current_admin.id,
            action="document.downloaded",
            resource_type="document",
            resource_id=doc.id,
            details={"filename": doc.original_filename}
        ))
        await db.commit()
        
        fallback = re.sub(r'[^A-Za-z0-9._-]+', "_", doc.original_filename or "document")
        encoded = quote(doc.original_filename or "document")
        return StreamingResponse(
            s3_response["Body"],
            media_type=doc.mime_type or "application/octet-stream",
            headers={
                "Content-Disposition": (
                    f'attachment; filename="{fallback}"; filename*=UTF-8\'\'{encoded}'
                )
            },
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
    current_admin: CurrentAdmin = Depends(require_admin_or_above),
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
    current_admin: CurrentAdmin = Depends(require_superadmin),
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
    
    db.add(AuditLog(
        admin_id=current_admin.id,
        action="document.deleted",
        resource_type="document",
        resource_id=doc_id,
        details={"filename": doc.original_filename}
    ))
    
    await db.commit()
    
    return {"detail": f"Document '{doc.original_filename}' and associated chunks deleted successfully."}
