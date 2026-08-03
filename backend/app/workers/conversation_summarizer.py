"""
╔══════════════════════════════════════════════════════════════════╗
║  VIDHYA BOT — Conversation Summarizer Worker (Phase 5)           ║
║  Celery task triggered when messages_since_summary hits the      ║
║  plan's summary_frequency threshold:                             ║
║    1. Fetches the last N unsummarized messages                   ║
║    2. Calls Ollama (qwen3:4b) for a concise rolling summary      ║
║    3. Saves summary_text to the Conversation row                 ║
║    4. Resets messages_since_summary counter                      ║
╚══════════════════════════════════════════════════════════════════╝
"""

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
MISTRAL_API_KEY    = os.getenv("MISTRAL_API_KEY", "")
MISTRAL_CHAT_MODEL  = os.getenv("MISTRAL_CHAT_MODEL", "mistral-small-latest")

# Max messages to include in summarization window
SUMMARIZE_WINDOW = 20


def get_engine():
    return create_engine(DATABASE_URL_SYNC, pool_pre_ping=True)


def call_mistral_summary(messages_text: str) -> str:
    """
    Send a summarization prompt to Mistral and return the summary text.
    Uses non-streaming mode for simplicity inside a sync Celery task.
    """
    url = "https://api.mistral.ai/v1/chat/completions"
    system = (
        "You are a concise summarizer. "
        "Given a conversation excerpt, produce a brief 2-4 sentence summary "
        "capturing the key topics and any answers given. "
        "Output only the summary, nothing else."
    )
    payload = {
        "model": MISTRAL_CHAT_MODEL,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": f"Summarize this conversation:\n\n{messages_text}"},
        ],
        "temperature": 0.2,
        "max_tokens": 200,
    }
    headers = {
        "Authorization": f"Bearer {MISTRAL_API_KEY}",
        "Content-Type": "application/json"
    }
    resp = httpx.post(url, json=payload, headers=headers, timeout=60.0)
    resp.raise_for_status()
    return resp.json().get("choices", [{}])[0].get("message", {}).get("content", "").strip()


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
        # ── 1. Load Conversation ──────────────────────────────────────
        conv = db.get(Conversation, conv_uuid)
        if not conv:
            logger.warning(f"summarize_conversation: Conversation {conversation_id} not found")
            return {"status": "skipped", "reason": "not_found"}

        if conv.status != "active":
            logger.info(f"summarize_conversation: Conversation {conversation_id} is {conv.status}, skipping")
            return {"status": "skipped", "reason": conv.status}

        # ── 2. Fetch last N messages ──────────────────────────────────
        result = db.execute(
            select(Message)
            .where(Message.conversation_id == conv_uuid)
            .order_by(Message.created_at.desc())
            .limit(SUMMARIZE_WINDOW)
        )
        messages = list(reversed(result.scalars().all()))

        if not messages:
            return {"status": "skipped", "reason": "no_messages"}

        # ── 3. Build conversation transcript ─────────────────────────
        transcript_parts = []
        for msg in messages:
            role_label = "User" if msg.role == "user" else "Assistant"
            transcript_parts.append(f"{role_label}: {msg.content}")
        transcript = "\n".join(transcript_parts)

        # ── 4. Call Mistral for summary ────────────────────────────────
        try:
            summary = call_mistral_summary(transcript)
        except Exception as exc:
            logger.error(f"summarize_conversation: Mistral call failed: {exc}")
            raise self.retry(exc=exc)

        if not summary:
            return {"status": "skipped", "reason": "empty_summary"}

        # ── 5. Persist summary + reset counter ───────────────────────
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
