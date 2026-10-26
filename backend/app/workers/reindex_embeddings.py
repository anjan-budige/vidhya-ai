"""
Re-index every active document with the current embedding model.

Re-downloads each PDF from MinIO, re-extracts, re-chunks, re-embeds and
replaces its chunks. Progress is written to platform_settings so the admin
panel can show status.
"""

import logging
import os
from datetime import datetime, timezone

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.models.document import Document
from app.models.platform_setting import PlatformSetting
from app.workers.celery_app import celery_app
from app.workers.pdf_ingest import ingest_document

logger = logging.getLogger(__name__)

DATABASE_URL_SYNC = os.getenv(
    "DATABASE_URL_SYNC",
    "postgresql://vidhya:CHANGE_ME@postgres:5432/vidhya_db",
)


@celery_app.task(
    name="vidhya.reindex_embeddings",
    queue="pdf",
    acks_late=True,
)
def reindex_embeddings(target_model_id: str):
    from app.services.ai_providers import AIProviderService

    engine = create_engine(DATABASE_URL_SYNC, pool_pre_ping=True)
    now = datetime.now(timezone.utc)

    with Session(engine) as db:
        state = db.get(PlatformSetting, 1)
        if not state:
            logger.error("reindex_embeddings: platform settings row missing")
            return {"status": "error", "detail": "Platform settings missing"}

        state.reindex_status = "running"
        state.reindex_started_at = now
        state.reindex_completed_at = None
        state.reindex_error = None
        db.commit()

        try:
            config = AIProviderService.get_default_sync("embedding")
        except Exception as exc:
            state.reindex_status = "failed"
            state.reindex_error = str(exc)[:500]
            state.reindex_completed_at = datetime.now(timezone.utc)
            db.commit()
            return {"status": "failed", "detail": str(exc)}

        if config.model_id != target_model_id:
            detail = "The default embedding model changed during re-indexing."
            state.reindex_status = "failed"
            state.reindex_error = detail
            state.reindex_completed_at = datetime.now(timezone.utc)
            db.commit()
            return {"status": "failed", "detail": detail}

        documents = (
            db.execute(
                select(Document).where(Document.is_active.is_(True))
            ).scalars().all()
        )
        total = len(documents)
        state.reindex_total = total
        state.reindex_done = 0
        state.reindex_failed = 0
        db.commit()

        done = 0
        failed = 0

        for doc in documents:
            try:
                result = ingest_document(
                    str(doc.id), force=True, embedding_config=config
                )
                if result.get("status") == "error":
                    failed += 1
                    logger.error("Re-index skipped for %s: %s", doc.id, result)
                else:
                    done += 1
            except Exception as exc:
                failed += 1
                logger.error("Re-index failed for document %s: %s", doc.id, exc)

            state.reindex_done = done
            state.reindex_failed = failed
            db.commit()

        state.reindex_status = "completed" if done > 0 or total == 0 else "failed"
        state.reindex_completed_at = datetime.now(timezone.utc)
        if failed:
            state.reindex_error = f"{failed} document(s) failed. Check worker logs."
        db.commit()

        logger.info(
            "reindex_embeddings complete: total=%s done=%s failed=%s model=%s",
            total,
            done,
            failed,
            config.model,
        )
        return {
            "status": state.reindex_status,
            "total": total,
            "done": done,
            "failed": failed,
        }
