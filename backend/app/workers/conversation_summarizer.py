import logging
import os
import uuid
from datetime import datetime, timezone

import httpx
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.models.conversation import Conversation
from app.models.message import Message
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)

DATABASE_URL_SYNC = os.getenv(
    "DATABASE_URL_SYNC",
    "postgresql://vidhya:CHANGE_ME@postgres:5432/vidhya_db"
)
SUMMARIZE_WINDOW = 20


def get_engine():
    return create_engine(DATABASE_URL_SYNC, pool_pre_ping=True)


def call_mistral_summary(messages_text: str) -> str:
    """Summarize a conversation with the configured chat provider."""
    from app.services.ai_providers import AIProviderService

    system = (
        "You are a concise summarizer. "
        "Given a conversation excerpt, produce a brief 2-4 sentence summary "
        "capturing the key topics and any answers given. "
        "Output only the summary, nothing else."
    )
    config = AIProviderService.get_default_sync("chat")
    return AIProviderService.complete_sync(
        config,
        [
            {"role": "system", "content": system},
            {
                "role": "user",
                "content": f"Summarize this conversation:\n\n{messages_text}",
            },
        ],
        max_tokens=200,
        temperature=0.2,
    )


@celery_app.task(
    name="vidhya.summarize_conversation",
    bind=True,
    queue="conversations",
    max_retries=2,
    default_retry_delay=30,
    acks_late=True,
)
def summarize_conversation(self, conversation_id: str):
    """
    Rolling summarizer for a single conversation.
    Triggered by ConversationService when messages_since_summary hits threshold.
    """
    conv_uuid = uuid.UUID(conversation_id)
    engine = get_engine()

    with Session(engine) as db:
        conv = db.get(Conversation, conv_uuid)
        if not conv:
            logger.warning(f"summarize_conversation: Conversation {conversation_id} not found")
            return {"status": "skipped", "reason": "not_found"}

        # Sessions have no active/closed lifecycle.
        result = db.execute(
            select(Message)
            .where(Message.conversation_id == conv_uuid)
            .order_by(Message.created_at.desc())
            .limit(SUMMARIZE_WINDOW)
        )
        messages = list(reversed(result.scalars().all()))

        if not messages:
            return {"status": "skipped", "reason": "no_messages"}

        transcript_parts = []
        for msg in messages:
            role_label = "User" if msg.role == "user" else "Assistant"
            transcript_parts.append(f"{role_label}: {msg.content}")
        transcript = "\n".join(transcript_parts)

        try:
            summary = call_mistral_summary(transcript)
        except Exception as exc:
            logger.error(f"summarize_conversation: Mistral call failed: {exc}")
            raise self.retry(exc=exc)

        if not summary:
            return {"status": "skipped", "reason": "empty_summary"}

        conv.summary_text = summary
        conv.last_summary_at = datetime.now(timezone.utc)
        conv.messages_since_summary = 0
        db.commit()

        logger.info(
            f"summarize_conversation: Saved summary for {conversation_id} "
            f"({len(messages)} msgs → {len(summary)} chars)"
        )
        return {
            "status": "summarized",
            "conversation_id": conversation_id,
            "messages_summarized": len(messages),
            "summary_length": len(summary),
        }
