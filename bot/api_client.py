"""
Vidhya Bot — API Client
Single HTTPX AsyncClient that all handlers use to call the FastAPI backend.
Handles session injection, SSE streaming, and error translation.
"""

import json
import logging
from typing import AsyncGenerator, Optional

import httpx

from config import get_settings

settings = get_settings()
logger = logging.getLogger("vidhya.api")

# Shared client — created once, reused across all requests
_client: Optional[httpx.AsyncClient] = None


def get_client() -> httpx.AsyncClient:
    global _client
    if _client is None or _client.is_closed:
        _client = httpx.AsyncClient(
            base_url=settings.BACKEND_URL,
            timeout=httpx.Timeout(connect=10.0, read=120.0, write=10.0, pool=5.0),
            headers={"Accept": "application/json", "Content-Type": "application/json"},
        )
    return _client


async def close_client():
    global _client
    if _client and not _client.is_closed:
        await _client.aclose()
        _client = None


# ── Auth Helpers ──────────────────────────────────────────────────────────────

async def telegram_login(init_data: str) -> dict:
    """Register/login Telegram user. Returns {session_token, user_id, is_new_user, plan_name}."""
    client = get_client()
    resp = await client.post(
        "/api/v1/auth/telegram/login",
        json={"init_data": init_data}
    )
    resp.raise_for_status()
    # CRITICAL: Clear cookie jar to prevent cross-user session leaks.
    # The backend's Set-Cookie response would otherwise persist in the
    # shared client and override other users' Authorization headers.
    client.cookies.clear()
    return resp.json()


# ── Subscription ──────────────────────────────────────────────────────────────

async def activate_free_plan(session_token: str) -> dict:
    client = get_client()
    resp = await client.post(
        "/api/v1/subscriptions/free/activate",
        headers={"Authorization": f"Bearer {session_token}"}
    )
    client.cookies.clear()  # Prevent cookie jar contamination
    if resp.status_code == 409:
        return {"already_active": True}
    resp.raise_for_status()
    return resp.json()


async def get_my_subscription(session_token: str) -> dict:
    client = get_client()
    resp = await client.get(
        "/api/v1/subscriptions/me",
        headers={"Authorization": f"Bearer {session_token}"}
    )
    client.cookies.clear()
    resp.raise_for_status()
    return resp.json()


# ── Plans ─────────────────────────────────────────────────────────────────────

async def get_plans() -> list:
    resp = await get_client().get("/api/v1/plans/")
    resp.raise_for_status()
    return resp.json()


# ── AI Quota ──────────────────────────────────────────────────────────────────

async def get_ai_quota(session_token: str) -> dict:
    client = get_client()
    resp = await client.get(
        "/api/v1/ai/quota",
        headers={"Authorization": f"Bearer {session_token}"}
    )
    client.cookies.clear()
    resp.raise_for_status()
    return resp.json()


# ── Conversations ─────────────────────────────────────────────────────────────

async def create_conversation(session_token: str, title: str = "Chat") -> dict:
    client = get_client()
    resp = await client.post(
        "/api/v1/conversations/",
        headers={"Authorization": f"Bearer {session_token}"},
        json={"title": title}
    )
    client.cookies.clear()
    resp.raise_for_status()
    return resp.json()


async def list_conversations(session_token: str) -> list:
    client = get_client()
    resp = await client.get(
        "/api/v1/conversations/",
        headers={"Authorization": f"Bearer {session_token}"}
    )
    client.cookies.clear()
    resp.raise_for_status()
    return resp.json()


async def close_conversation(session_token: str, conv_id: str) -> dict:
    client = get_client()
    resp = await client.post(
        f"/api/v1/conversations/{conv_id}/close",
        headers={"Authorization": f"Bearer {session_token}"}
    )
    client.cookies.clear()
    resp.raise_for_status()
    return resp.json()

async def delete_conversation(session_token: str, conv_id: str) -> dict:
    client = get_client()
    resp = await client.delete(
        f"/api/v1/conversations/{conv_id}",
        headers={"Authorization": f"Bearer {session_token}"}
    )
    client.cookies.clear()
    resp.raise_for_status()
    return resp.json()


# ── Payment ───────────────────────────────────────────────────────────────────

async def initiate_payment(session_token: str, plan_id: str, amount_paise: int) -> dict:
    client = get_client()
    resp = await client.post(
        "/api/v1/payments/initiate",
        headers={"Authorization": f"Bearer {session_token}"},
        json={"plan_id": plan_id, "amount": amount_paise}
    )
    client.cookies.clear()
    resp.raise_for_status()
    return resp.json()


# ── AI SSE Stream ─────────────────────────────────────────────────────────────

async def stream_ai_response(
    session_token: str,
    message: str,
    conversation_id: str,
) -> AsyncGenerator[str, None]:
    """
    Streams SSE token events from the backend AI chat endpoint.
    Yields individual token strings as they arrive.
    """
    client = get_client()
    async with client.stream(
        "POST",
        "/api/v1/ai/chat/stream",
        headers={
            "Authorization": f"Bearer {session_token}",
            "Accept": "text/event-stream",
        },
        json={"message": message, "conversation_id": conversation_id},
        timeout=httpx.Timeout(connect=10.0, read=300.0, write=10.0, pool=5.0),
    ) as response:
        if response.is_error:
            await response.aread()
        response.raise_for_status()
        async for line in response.aiter_lines():
            if not line:
                continue
            if line.startswith("data: "):
                raw = line[6:]
                try:
                    data = json.loads(raw)
                    token = data.get("token")
                    if token:
                        yield token
                    # Stop on done event
                    if data.get("status") == "completed":
                        return
                    # Propagate errors
                    if "detail" in data:
                        yield f"\n\n⚠️ {data['detail']}"
                        return
                except Exception:
                    pass
