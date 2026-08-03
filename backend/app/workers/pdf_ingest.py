"""
╔══════════════════════════════════════════════════════════════════╗
║  VIDHYA BOT — PDF Ingestion Worker (Phase 5)                     ║
║  Celery task that processes uploaded PDFs:                        ║
║    1. Downloads PDF from MinIO                                    ║
║    2. Extracts text page-by-page via pypdf                        ║
║    3. Chunks text with sliding overlap window                     ║
║    4. Generates 768d embeddings via Ollama nomic-embed-text       ║
║    5. Writes DocumentChunk rows to Postgres                       ║
║    6. Updates Document.status → processed / failed               ║
╚══════════════════════════════════════════════════════════════════╝
"""

import io
import logging
import math
import os
import uuid
from datetime import datetime, timezone

import boto3
import httpx
from botocore.client import Config
from pypdf import PdfReader
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.models.chunk import DocumentChunk
from app.models.document import Document
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)

# ── Sync DB Engine (Celery tasks use sync SQLAlchemy) ────────────────────────
DATABASE_URL_SYNC = os.getenv(
    "DATABASE_URL_SYNC",
    "postgresql://vidhya:CHANGE_ME@postgres:5432/vidhya_db"
)

# ── MinIO / S3 Config ────────────────────────────────────────────────────────
MINIO_ENDPOINT   = os.getenv("MINIO_ENDPOINT", "http://minio:9000")
MINIO_ACCESS_KEY = os.getenv("MINIO_ROOT_USER", "minioadmin")
MINIO_SECRET_KEY = os.getenv("MINIO_ROOT_PASSWORD", "")
MINIO_BUCKET     = os.getenv("MINIO_BUCKET", "vidhya-documents")

# ── Mistral API Config ────────────────────────────────────────────────────────
MISTRAL_API_KEY   = os.getenv("MISTRAL_API_KEY", "")
MISTRAL_EMBED_MODEL = os.getenv("MISTRAL_EMBED_MODEL", "mistral-embed")

# ── Chunking Parameters ───────────────────────────────────────────────────────
CHUNK_SIZE_CHARS   = 800    # characters per chunk
CHUNK_OVERLAP_CHARS = 150   # overlap between consecutive chunks


def get_s3_client():
    return boto3.client(
        "s3",
        endpoint_url=MINIO_ENDPOINT,
        aws_access_key_id=MINIO_ACCESS_KEY,
        aws_secret_access_key=MINIO_SECRET_KEY,
        config=Config(signature_version="s3v4", s3={'addressing_style': 'path'}),
        region_name="us-east-1",
    )


def generate_embedding_sync(text: str) -> list:
    """Generate embedding synchronously via Mistral REST API."""
    url = "https://api.mistral.ai/v1/embeddings"
    payload = {"model": MISTRAL_EMBED_MODEL, "input": [text]}
    headers = {
        "Authorization": f"Bearer {MISTRAL_API_KEY}",
        "Content-Type": "application/json"
    }
    try:
        resp = httpx.post(url, json=payload, headers=headers, timeout=30.0)
        resp.raise_for_status()
        res_json = resp.json()
        
        embedding = res_json.get("data", [{}])[0].get("embedding")
        if not embedding or not isinstance(embedding, list):
            raise ValueError("Mistral response does not contain a valid embedding vector.")
            
        return embedding
    except Exception as exc:
        logger.error(f"Embedding generation failed: {exc}")
        return []


def chunk_text(text: str, page_number: int) -> list[dict]:
    """
    Split text into overlapping chunks.
    Returns list of dicts with keys: content, chunk_index, page_number, token_count
    """
    chunks = []
    start = 0
    idx = 0
    text = text.strip()
    if not text:
        return chunks

    while start < len(text):
        end = min(start + CHUNK_SIZE_CHARS, len(text))
        chunk_content = text[start:end].strip()
        if chunk_content:
            # Approximate token count (1 token ≈ 4 chars)
            token_count = max(1, len(chunk_content) // 4)
            chunks.append({
                "content": chunk_content,
                "chunk_index": idx,
                "page_number": page_number,
                "token_count": token_count,
            })
            idx += 1
        start += CHUNK_SIZE_CHARS - CHUNK_OVERLAP_CHARS

    return chunks


@celery_app.task(
    name="vidhya.ingest_pdf",
    bind=True,
    queue="pdf",
    max_retries=3,
    default_retry_delay=60,
    acks_late=True,
)
def ingest_pdf(self, document_id: str):
    """
    Main PDF ingestion pipeline.
    Called by the document upload router after a file is saved to MinIO.
    """
    doc_uuid = uuid.UUID(document_id)
    engine = create_engine(DATABASE_URL_SYNC, pool_pre_ping=True)

    with Session(engine) as db:
        # ── 1. Load Document record ───────────────────────────────────────
        doc = db.get(Document, doc_uuid)
        if not doc:
            logger.error(f"ingest_pdf: Document {document_id} not found in DB")
            return {"status": "error", "detail": "Document not found"}

        # Mark as processing
        doc.status = "processing"
        db.commit()

        try:
            # ── 2. Download PDF from MinIO ────────────────────────────────
            s3 = get_s3_client()
            obj = s3.get_object(Bucket=doc.s3_bucket, Key=doc.s3_key)
            pdf_bytes = obj["Body"].read()

            # ── 3. Extract text per page ─────────────────────────────────
            reader = PdfReader(io.BytesIO(pdf_bytes))
            total_pages = len(reader.pages)
            all_chunks = []

            for page_idx, page in enumerate(reader.pages):
                page_number = page_idx + 1
                try:
                    page_text = page.extract_text() or ""
                    # PostgreSQL does not accept NUL bytes (0x00) in text fields
                    page_text = page_text.replace("\x00", "").replace("\0", "")
                except Exception:
                    page_text = ""

                if not page_text.strip():
                    continue

                page_chunks = chunk_text(page_text, page_number)
                all_chunks.extend(page_chunks)

            if not all_chunks:
                raise ValueError("PDF contained no extractable text")

            # ── 3.5. Fetch existing chunks to support resumption ───────────
            from sqlalchemy import select
            existing_chunks_stmt = select(DocumentChunk.chunk_index).where(DocumentChunk.document_id == doc_uuid)
            existing_indices_result = db.execute(existing_chunks_stmt)
            existing_indices = set(existing_indices_result.scalars().all())

            # Update status to chunked while embeddings are generating
            doc.status = "chunked"
            doc.total_chunks = len(all_chunks)
            doc.processed_chunks = len(existing_indices)
            db.commit()

            # ── 4. Generate embeddings + persist chunks ───────────────────
            chunk_records = []
            import time
            
            for idx, chunk_data in enumerate(all_chunks):
                if chunk_data["chunk_index"] in existing_indices:
                    continue  # Skip already embedded chunks!

                # Basic backoff loop for 429 Too Many Requests
                max_retries = 10  # Increased retries since we resume perfectly
                embedding = None
                for attempt in range(max_retries):
                    try:
                        embedding = generate_embedding_sync(chunk_data["content"])
                        break
                    except Exception as e:
                        if "429" in str(e) and attempt < max_retries - 1:
                            logger.warning(f"Rate limited by Mistral (429). Retrying in {2 ** attempt}s...")
                            time.sleep(2 ** attempt)
                        else:
                            raise e
                

                chunk = DocumentChunk(
                    document_id=doc_uuid,
                    chunk_index=chunk_data["chunk_index"],
                    content=chunk_data["content"],
                    token_count=chunk_data["token_count"],
                    page_number=chunk_data["page_number"],
                    embedding=embedding if embedding else None,
                    created_at=datetime.now(timezone.utc),
                )
                db.add(chunk)
                doc.processed_chunks = idx + 1
                db.commit()  # Save progress immediately so we never lose it

            # ── 5. Update Document record ─────────────────────────────────
            doc.status = "processed"
            doc.total_chunks = len(all_chunks)
            doc.processed_chunks = len(all_chunks)
            doc.total_pages = total_pages
            doc.processed_at = datetime.now(timezone.utc)
            doc.processing_error = None

            db.commit()

            logger.info(
                f"ingest_pdf: Processed document {document_id} — "
                f"{total_pages} pages, {len(all_chunks)} chunks"
            )
            return {
                "status": "processed",
                "document_id": document_id,
                "total_pages": total_pages,
                "total_chunks": len(all_chunks),
            }

        except Exception as exc:
            logger.error(f"ingest_pdf: Failed for {document_id}: {exc}", exc_info=True)
            try:
                doc.status = "failed"
                doc.processing_error = str(exc)[:500]
                db.commit()
            except Exception:
                db.rollback()

            # Retry on transient errors
            raise self.retry(exc=exc)
