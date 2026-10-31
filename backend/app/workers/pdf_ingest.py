"""
Vidhya Bot — PDF ingestion.

Downloads a PDF from MinIO, extracts text, chunks it, embeds every chunk with
the active embedding model (recorded on each chunk), and stores the vectors.

`ingest_document()` is a plain function so the re-index job can reuse it.
"""

import io
import logging
import os
import time
import uuid
from datetime import datetime, timezone

import boto3
from botocore.client import Config
from pypdf import PdfReader
from sqlalchemy import create_engine, delete, select
from sqlalchemy.orm import Session

from app.models.chunk import DocumentChunk
from app.models.document import Document
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)

DATABASE_URL_SYNC = os.getenv(
    "DATABASE_URL_SYNC",
    "postgresql://vidhya:CHANGE_ME@postgres:5432/vidhya_db",
)

MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT", "http://minio:9000")
MINIO_ACCESS_KEY = os.getenv("MINIO_ROOT_USER", "minioadmin")
MINIO_SECRET_KEY = os.getenv("MINIO_ROOT_PASSWORD", "")
MINIO_BUCKET = os.getenv("MINIO_BUCKET", "vidhya-documents")

CHUNK_SIZE_CHARS = 800
CHUNK_OVERLAP_CHARS = 150


def get_s3_client():
    return boto3.client(
        "s3",
        endpoint_url=MINIO_ENDPOINT,
        aws_access_key_id=MINIO_ACCESS_KEY,
        aws_secret_access_key=MINIO_SECRET_KEY,
        config=Config(signature_version="s3v4", s3={"addressing_style": "path"}),
        region_name="us-east-1",
    )


def chunk_text(text: str, page_number: int) -> list[dict]:
    """Split text into overlapping chunks."""
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
            chunks.append(
                {
                    "content": chunk_content,
                    "chunk_index": idx,
                    "page_number": page_number,
                    "token_count": max(1, len(chunk_content) // 4),
                }
            )
            idx += 1
        start += CHUNK_SIZE_CHARS - CHUNK_OVERLAP_CHARS

    return chunks


def ingest_document(document_id: str, force: bool = False, embedding_config=None) -> dict:
    """Ingest or re-ingest one document from MinIO."""
    from app.services.ai_providers import AIProviderService

    doc_uuid = uuid.UUID(document_id)
    engine = create_engine(DATABASE_URL_SYNC, pool_pre_ping=True)

    if embedding_config is None:
        embedding_config = AIProviderService.get_default_sync("embedding")

    with Session(engine) as db:
        doc = db.get(Document, doc_uuid)
        if not doc:
            logger.error("ingest_document: document %s not found", document_id)
            return {"status": "error", "detail": "Document not found"}

        doc.status = "processing"
        db.commit()

        try:
            s3 = get_s3_client()
            obj = s3.get_object(Bucket=doc.s3_bucket, Key=doc.s3_key)
            file_bytes = obj["Body"].read()

            extension = (
                "." + doc.original_filename.rsplit(".", 1)[-1].lower()
                if "." in doc.original_filename
                else ""
            )
            all_chunks = []

            if extension == ".pdf":
                reader = PdfReader(io.BytesIO(file_bytes))
                total_pages = len(reader.pages)
                for page_idx, page in enumerate(reader.pages):
                    try:
                        page_text = page.extract_text() or ""
                        page_text = page_text.replace("\x00", "").replace("\0", "")
                    except Exception:
                        page_text = ""
                    if page_text.strip():
                        all_chunks.extend(chunk_text(page_text, page_idx + 1))
            else:
                # Plain-text family: no pagination, so everything is page 1.
                total_pages = 1
                try:
                    text = file_bytes.decode("utf-8")
                except UnicodeDecodeError:
                    text = file_bytes.decode("latin-1")
                text = text.replace("\x00", "")
                if text.strip():
                    all_chunks.extend(chunk_text(text, 1))

            if not all_chunks:
                raise ValueError("Document contained no extractable text")

            existing_indices = set()
            if force:
                # Only drop old vectors after the PDF was downloaded and parsed.
                db.execute(
                    delete(DocumentChunk).where(
                        DocumentChunk.document_id == doc_uuid
                    )
                )
            else:
                existing_indices = set(
                    db.execute(
                        select(DocumentChunk.chunk_index).where(
                            DocumentChunk.document_id == doc_uuid
                        )
                    ).scalars().all()
                )

            doc.status = "chunked"
            doc.total_chunks = len(all_chunks)
            doc.processed_chunks = len(existing_indices)
            db.commit()

            pending = [
                chunk
                for chunk in all_chunks
                if chunk["chunk_index"] not in existing_indices
            ]
            model_uuid = (
                uuid.UUID(embedding_config.model_id)
                if embedding_config.model_id
                else None
            )
            batch_size = 16
            completed = len(existing_indices)

            for offset in range(0, len(pending), batch_size):
                batch = pending[offset : offset + batch_size]
                embeddings = None
                for attempt in range(8):
                    try:
                        embeddings = AIProviderService.embed_many_sync(
                            embedding_config, [c["content"] for c in batch]
                        )
                        break
                    except Exception as exc:
                        if "429" in str(exc) and attempt < 7:
                            delay = min(60, 2 ** attempt)
                            logger.warning(
                                "Rate limited while embedding; retrying in %ss",
                                delay,
                            )
                            time.sleep(delay)
                        else:
                            raise

                for chunk_data, embedding in zip(batch, embeddings or []):
                    db.add(
                        DocumentChunk(
                            document_id=doc_uuid,
                            chunk_index=chunk_data["chunk_index"],
                            content=chunk_data["content"],
                            token_count=chunk_data["token_count"],
                            page_number=chunk_data["page_number"],
                            embedding=embedding,
                            embedding_model_id=model_uuid,
                            created_at=datetime.now(timezone.utc),
                        )
                    )
                completed += len(batch)
                doc.processed_chunks = completed
                db.commit()
                time.sleep(0.5)

            doc.status = "processed"
            doc.total_chunks = len(all_chunks)
            doc.processed_chunks = len(all_chunks)
            doc.total_pages = total_pages
            doc.processed_at = datetime.now(timezone.utc)
            doc.processing_error = None
            db.commit()

            logger.info(
                "ingest_document: %s — %s pages, %s chunks (model %s)",
                document_id,
                total_pages,
                len(all_chunks),
                embedding_config.model,
            )
            return {
                "status": "processed",
                "document_id": document_id,
                "total_pages": total_pages,
                "total_chunks": len(all_chunks),
            }

        except Exception as exc:
            logger.error("ingest_document failed for %s: %s", document_id, exc)
            try:
                doc.status = "failed"
                doc.processing_error = str(exc)[:500]
                db.commit()
            except Exception:
                db.rollback()
            raise


@celery_app.task(
    name="vidhya.ingest_pdf",
    bind=True,
    queue="pdf",
    max_retries=3,
    default_retry_delay=60,
    acks_late=True,
)
def ingest_pdf(self, document_id: str):
    try:
        return ingest_document(document_id)
    except Exception as exc:
        raise self.retry(exc=exc)
