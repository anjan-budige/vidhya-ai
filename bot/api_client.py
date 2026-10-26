"""Vidhya Bot — backend API client.

Every user-scoped request authenticates with the user's API key plus the
server-only bot bridge token. The bridge token prevents those keys from being
reused by browsers or raw HTTP clients.
"""

import hashlib
import hmac
import json
from typing import AsyncGenerator, Optional

import httpx

from config import get_settings

settings = get_settings()

_BOT_CONTEXT = b"vidhya:internal:telegram-bot:v1"
_BOT_TOKEN = hmac.new(
    settings.SECRET_KEY.encode("utf-8"), _BOT_CONTEXT, hashlib.sha256
).hexdigest()

_client: Optional[httpx.AsyncClient] = None


def get_client() -> httpx.AsyncClient:
    global _client
    if _client is None or _client.is_closed:
        _client = httpx.AsyncClient(base_url=settings.BACKEND_URL, timeout=60.0)
    return _client


async def close_client() -> None:
    global _client
    if _client and not _client.is_closed:
        await _client.aclose()
        _client = None


def _headers(api_key: str) -> dict:
    return {
        "X-API-Key": api_key,
        "X-Bot-Token": _BOT_TOKEN,
    }



async def get_platform_config() -> dict:
    resp = await get_client().get("/api/v1/config/public")
    resp.raise_for_status()
    return resp.json()



async def get_me(api_key: str) -> dict:
    resp = await get_client().get("/api/v1/auth/me", headers=_headers(api_key))
    resp.raise_for_status()
    return resp.json()


async def link_api_key(api_key: str, telegram_id: int) -> dict:
    resp = await get_client().post(
        "/api/v1/auth/api-key/link",
        json={"telegram_id": telegram_id},
        headers=_headers(api_key),
    )
    resp.raise_for_status()
    return resp.json()



async def create_conversation(api_key: str, title: Optional[str] = None) -> dict:
    resp = await get_client().post(
        "/api/v1/conversations/",
        json={"title": title},
        headers=_headers(api_key),
    )
    resp.raise_for_status()
    return resp.json()


async def list_conversations(api_key: str) -> list:
    resp = await get_client().get(
        "/api/v1/conversations/?page=1&page_size=50",
        headers=_headers(api_key),
    )
    resp.raise_for_status()
    return resp.json()


async def get_conversation(api_key: str, conv_id: str) -> dict:
    resp = await get_client().get(
        f"/api/v1/conversations/{conv_id}", headers=_headers(api_key)
    )
    resp.raise_for_status()
    return resp.json()


async def delete_conversation(api_key: str, conv_id: str) -> dict:
    resp = await get_client().delete(
        f"/api/v1/conversations/{conv_id}", headers=_headers(api_key)
    )
    resp.raise_for_status()
    return resp.json()



async def get_ai_quota(api_key: str) -> dict:
    resp = await get_client().get("/api/v1/ai/quota", headers=_headers(api_key))
    resp.raise_for_status()
    return resp.json()


async def get_my_subscription(api_key: str) -> dict:
    resp = await get_client().get(
        "/api/v1/subscriptions/me", headers=_headers(api_key)
    )
    resp.raise_for_status()
    return resp.json()



async def stream_ai_response(
    api_key: str, message: str, conversation_id: Optional[str]
) -> AsyncGenerator[dict, None]:
    """
    Yield dicts:
      {"type": "token", "text": "..."}
      {"type": "error", "code": "context_limit"|..., "detail": "..."}
      {"type": "metadata", "conversation_id": "..."}
      {"type": "done"}
    """
    payload = {"message": message}
    if conversation_id:
        payload["conversation_id"] = conversation_id

    async with get_client().stream(
        "POST",
        "/api/v1/ai/chat/stream",
        json=payload,
        headers=_headers(api_key),
    ) as resp:
        if resp.status_code >= 400:
            body = await resp.aread()
            detail = "Request failed."
            try:
                detail = json.loads(body).get("detail", detail)
            except Exception:
                pass
            yield {
                "type": "error",
                "code": "http",
                "status": resp.status_code,
                "detail": detail,
            }
            return

        event = None
        async for line in resp.aiter_lines():
            if line.startswith("event:"):
                event = line.split(":", 1)[1].strip()
            elif line.startswith("data:"):
                raw = line.split(":", 1)[1].strip()
                try:
                    data = json.loads(raw)
                except Exception:
                    continue

                if event == "token":
                    yield {"type": "token", "text": data.get("token", "")}
                elif event == "error":
                    yield {
                        "type": "error",
                        "code": data.get("code"),
                        "detail": data.get("detail", "AI error."),
                    }
                    return
                elif event == "metadata":
                    yield {
                        "type": "metadata",
                        "conversation_id": data.get("conversation_id"),
                    }
                elif event == "done":
                    yield {"type": "done"}
                    return
