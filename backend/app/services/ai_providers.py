"""
Vidhya AI — provider and model resolution.

Chat models and embedding models live in separate tables:
  ai_chat_models      — may have several active; one is the default
  ai_embedding_models — exactly one active, enforced by a unique index

FastAPI uses the async accessors; Celery workers use the sync ones.
"""

import base64
import json
import logging
import time
from dataclasses import asdict, dataclass
from typing import Any, AsyncGenerator, Dict, List, Optional

import httpx
import redis.asyncio as aioredis
from sqlalchemy import create_engine, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models.ai_chat_model import AIChatModel
from app.models.ai_embedding_model import AIEmbeddingModel
from app.models.ai_provider import AIProvider
from app.models.platform_setting import PlatformSetting
from app.services.prompts import DEFAULT_SYSTEM_PROMPT
from app.utils.crypto import decrypt_secret

settings = get_settings()
logger = logging.getLogger("vidhya.ai_providers")

_sync_engine = None
_sync_cache: Dict[str, tuple] = {}


class AIConfigError(Exception):
    pass


@dataclass
class AIConfig:
    provider_id: str
    model_id: str
    provider_name: str
    adapter: str
    base_url: str
    auth_type: str
    auth_key_name: Optional[str]
    auth_username: Optional[str]
    api_key: Optional[str]
    api_key_encrypted: Optional[str]
    model: str
    kind: str
    context_window: int
    max_output_tokens: int
    embedding_dimensions: Optional[int]
    system_prompt: str = ""
    chat_url: str = ""
    embeddings_url: str = ""
    models_url: str = ""


def _endpoint(cfg: AIConfig, kind: str) -> str:
    if kind == "chat" and cfg.chat_url:
        return cfg.chat_url.strip()
    if kind == "embedding" and cfg.embeddings_url:
        return cfg.embeddings_url.strip()
    if kind == "models" and cfg.models_url:
        return cfg.models_url.strip()
    suffix = {
        "chat": "/chat/completions",
        "embedding": "/embeddings",
        "models": "/models",
    }[kind]
    return f"{_base(cfg)}{suffix}"


def _base(cfg: AIConfig) -> str:
    return (cfg.base_url or "").rstrip("/")


def _headers(cfg: AIConfig) -> Dict[str, str]:
    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    key = cfg.api_key or ""
    if not key:
        return headers
    if cfg.auth_type == "bearer":
        headers["Authorization"] = f"Bearer {key}"
    elif cfg.auth_type == "header":
        headers[cfg.auth_key_name or "x-api-key"] = key
    elif cfg.auth_type == "basic":
        raw = f"{cfg.auth_username or ''}:{key}".encode("utf-8")
        headers["Authorization"] = f"Basic {base64.b64encode(raw).decode('ascii')}"
    return headers


def _params(cfg: AIConfig) -> Dict[str, str]:
    if cfg.auth_type == "query" and cfg.api_key:
        return {cfg.auth_key_name or "key": cfg.api_key}
    return {}


def _common(provider: AIProvider, model) -> Dict[str, Any]:
    try:
        key = (
            decrypt_secret(provider.api_key_encrypted)
            if provider.api_key_encrypted
            else None
        )
    except Exception:
        raise AIConfigError(
            f"Could not decrypt the API key for provider '{provider.name}'. "
            "Re-save the key in Admin → AI Providers."
        )
    return {
        "provider_id": str(provider.id),
        "model_id": str(model.id),
        "provider_name": provider.name,
        "adapter": provider.adapter,
        "base_url": provider.base_url,
        "chat_url": provider.chat_url or "",
        "embeddings_url": provider.embeddings_url or "",
        "models_url": provider.models_url or "",
        "auth_type": provider.auth_type,
        "auth_key_name": provider.auth_key_name,
        "auth_username": provider.auth_username,
        "api_key": key,
        "api_key_encrypted": provider.api_key_encrypted,
        "model": model.name,
    }


def _chat_label(provider: AIProvider, model: AIChatModel) -> AIConfig:
    return AIConfig(
        **_common(provider, model),
        kind="chat",
        context_window=model.context_window,
        max_output_tokens=model.max_output_tokens,
        embedding_dimensions=None,
        system_prompt=(model.system_prompt or "").strip() or DEFAULT_SYSTEM_PROMPT,
    )


def _embedding_label(provider: AIProvider, model: AIEmbeddingModel) -> AIConfig:
    return AIConfig(
        **_common(provider, model),
        kind="embedding",
        context_window=0,
        max_output_tokens=0,
        embedding_dimensions=model.embedding_dimensions,
    )


def _simple_message(messages: List[Dict[str, str]]) -> str:
    """Flatten a chat into the single `message` string used by simple APIs."""
    parts: List[str] = []
    for message in messages:
        role = (message.get("role") or "user").lower()
        content = (message.get("content") or "").strip()
        if not content:
            continue
        if role == "system":
            parts.append(content)
        elif role == "assistant":
            parts.append(f"Assistant: {content}")
        else:
            parts.append(f"User: {content}")
    return "\n\n".join(parts)


def _extract_text(data: Dict[str, Any]) -> str:
    if not isinstance(data, dict):
        return ""
    choices = data.get("choices")
    if isinstance(choices, list) and choices:
        message = choices[0].get("message") if isinstance(choices[0], dict) else None
        if isinstance(message, dict):
            return (message.get("content") or "").strip()
    for key in ("text", "response", "content", "answer", "message"):
        value = data.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _extract_vector(data: Dict[str, Any]) -> Optional[List[float]]:
    if not isinstance(data, dict):
        return None
    vector = data.get("embedding")
    if isinstance(vector, list) and vector:
        return vector
    rows = data.get("data")
    if isinstance(rows, list) and rows and isinstance(rows[0], dict):
        value = rows[0].get("embedding")
        if isinstance(value, list) and value:
            return value
    return None


class AIProviderService:

    @classmethod
    async def get_default(
        cls, db: AsyncSession, redis: aioredis.Redis, kind: str
    ) -> AIConfig:
        cache_key = f"ai:default:{kind}"
        cached = await redis.get(cache_key)
        if cached:
            try:
                data = json.loads(cached)
                encrypted = data.get("api_key_encrypted")
                data["api_key"] = decrypt_secret(encrypted) if encrypted else None
                data["api_key_encrypted"] = None
                return AIConfig(**data)
            except Exception:
                pass

        config = await cls._load_default(db, kind)
        payload = asdict(config)
        payload["api_key"] = None
        await redis.set(cache_key, json.dumps(payload), ex=120)
        return config

    @staticmethod
    async def _load_default(db: AsyncSession, kind: str) -> AIConfig:
        if kind == "chat":
            rows = (
                await db.execute(
                    select(AIChatModel, AIProvider)
                    .join(AIProvider, AIChatModel.provider_id == AIProvider.id)
                    .where(
                        AIChatModel.is_active.is_(True),
                        AIProvider.is_active.is_(True),
                    )
                )
            ).all()
            if not rows:
                raise AIConfigError(
                    "No active chat model is configured. Add one in Admin → AI Providers."
                )

            settings_row = (
                await db.execute(
                    select(PlatformSetting).where(PlatformSetting.id == 1)
                )
            ).scalar_one_or_none()
            default_id = settings_row.default_chat_model_id if settings_row else None
            chosen = next(
                ((m, p) for m, p in rows if default_id and m.id == default_id),
                None,
            )
            if not chosen:
                chosen = next(((m, p) for m, p in rows if m.is_default), rows[0])
            return _chat_label(chosen[1], chosen[0])

        row = (
            await db.execute(
                select(AIEmbeddingModel, AIProvider)
                .join(AIProvider, AIEmbeddingModel.provider_id == AIProvider.id)
                .where(
                    AIEmbeddingModel.is_active.is_(True),
                    AIProvider.is_active.is_(True),
                )
                .limit(1)
            )
        ).first()
        if not row:
            raise AIConfigError(
                "No active embedding model is configured. Activate one in Admin → AI Providers."
            )
        return _embedding_label(row[1], row[0])

    @staticmethod
    def get_default_sync(kind: str) -> AIConfig:
        """Worker accessor — 30 s in-process cache."""
        global _sync_engine

        cached = _sync_cache.get(kind)
        if cached and cached[0] > time.time():
            return cached[1]

        if _sync_engine is None:
            _sync_engine = create_engine(
                settings.DATABASE_URL_SYNC, pool_pre_ping=True
            )

        with Session(_sync_engine) as db:
            if kind == "chat":
                rows = db.execute(
                    select(AIChatModel, AIProvider)
                    .join(AIProvider, AIChatModel.provider_id == AIProvider.id)
                    .where(
                        AIChatModel.is_active.is_(True),
                        AIProvider.is_active.is_(True),
                    )
                ).all()
                if not rows:
                    raise AIConfigError(
                        "No active chat model is configured. Add one in Admin → AI Providers."
                    )
                settings_row = db.execute(
                    select(PlatformSetting).where(PlatformSetting.id == 1)
                ).scalar_one_or_none()
                default_id = (
                    settings_row.default_chat_model_id if settings_row else None
                )
                chosen = next(
                    ((m, p) for m, p in rows if default_id and m.id == default_id),
                    None,
                )
                if not chosen:
                    chosen = next(((m, p) for m, p in rows if m.is_default), rows[0])
                config = _chat_label(chosen[1], chosen[0])
            else:
                row = db.execute(
                    select(AIEmbeddingModel, AIProvider)
                    .join(AIProvider, AIEmbeddingModel.provider_id == AIProvider.id)
                    .where(
                        AIEmbeddingModel.is_active.is_(True),
                        AIProvider.is_active.is_(True),
                    )
                    .limit(1)
                ).first()
                if not row:
                    raise AIConfigError(
                        "No active embedding model is configured. Activate one in Admin → AI Providers."
                    )
                config = _embedding_label(row[1], row[0])

            _sync_cache[kind] = (time.time() + 30, config)
            return config

    @staticmethod
    async def invalidate(redis: aioredis.Redis) -> None:
        await redis.delete("ai:default:chat", "ai:default:embedding")
        _sync_cache.clear()


    @staticmethod
    async def fetch_models(
        base_url: str,
        auth_type: str,
        api_key: Optional[str],
        auth_key_name: Optional[str] = None,
        auth_username: Optional[str] = None,
        models_url: Optional[str] = None,
        adapter: str = "openai_compatible",
    ) -> List[Dict[str, str]]:
        cfg = AIConfig(
            provider_id="",
            model_id="",
            provider_name="",
            adapter=adapter,
            base_url=base_url,
            models_url=models_url or "",
            auth_type=auth_type,
            auth_key_name=auth_key_name,
            auth_username=auth_username,
            api_key=api_key,
            api_key_encrypted=None,
            model="",
            kind="chat",
            context_window=0,
            max_output_tokens=0,
            embedding_dimensions=None,
        )
        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.get(
                _endpoint(cfg, "models"),
                headers=_headers(cfg),
                params=_params(cfg),
            )
            response.raise_for_status()
            data = response.json()

        items = data.get("data") if isinstance(data, dict) else data
        if items is None and isinstance(data, dict):
            items = data.get("models")
        results = []
        for item in items or []:
            if isinstance(item, str):
                results.append({"id": item, "display_name": item})
            elif isinstance(item, dict):
                identifier = item.get("id") or item.get("name")
                if not identifier:
                    continue
                entry: Dict[str, Any] = {
                    "id": identifier,
                    "display_name": item.get("display_name") or identifier,
                }
                context = (
                    item.get("context_window")
                    or item.get("context_length")
                    or item.get("max_context_tokens")
                    or item.get("max_model_len")
                )
                output = (
                    item.get("max_output_tokens")
                    or item.get("max_completion_tokens")
                    or (item.get("top_provider") or {}).get("max_completion_tokens")
                )
                if isinstance(context, int) and context > 0:
                    entry["context_window"] = context
                if isinstance(output, int) and output > 0:
                    entry["max_output_tokens"] = output
                results.append(entry)
        return results

    @staticmethod
    async def test_chat(config: AIConfig) -> Dict[str, Any]:
        started = time.time()
        question = "What is the capital of India?"
        if config.adapter == "custom":
            payload: Dict[str, Any] = {"message": question, "model": config.model}
        else:
            payload = {
                "model": config.model,
                "messages": [{"role": "user", "content": question}],
                "temperature": 0,
                "max_tokens": 64,
            }
        async with httpx.AsyncClient(timeout=45.0) as client:
            response = await client.post(
                _endpoint(config, "chat"),
                headers=_headers(config),
                params=_params(config),
                json=payload,
            )
            response.raise_for_status()
            data = response.json()
        answer = _extract_text(data)
        if not answer:
            raise AIConfigError("The provider returned an empty answer.")
        return {
            "ok": True,
            "answer": answer,
            "latency_ms": round((time.time() - started) * 1000),
        }

    @staticmethod
    async def test_embedding(config: AIConfig) -> Dict[str, Any]:
        """Embed a short fixed text. Nothing is written to the database."""
        started = time.time()
        vector = await AIProviderService.embed(config, "Vidhya AI embedding test")
        return {
            "ok": True,
            "dimensions": len(vector),
            "latency_ms": round((time.time() - started) * 1000),
        }


    @staticmethod
    async def embed(config: AIConfig, text: str) -> List[float]:
        payload = {"model": config.model, "input": [text]}
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                _endpoint(config, "embedding"),
                headers=_headers(config),
                params=_params(config),
                json=payload,
            )
            response.raise_for_status()
            data = response.json()
        vector = _extract_vector(data)
        if not vector:
            raise AIConfigError("Embedding response is empty.")
        if config.embedding_dimensions and len(vector) != config.embedding_dimensions:
            raise AIConfigError(
                f"Embedding dimension mismatch: model returned {len(vector)}, "
                f"but it is configured for {config.embedding_dimensions} dimensions."
            )
        return vector

    @staticmethod
    def embed_many_sync(config: AIConfig, texts: List[str]) -> List[List[float]]:
        """Embed several texts in one request, falling back to single calls."""
        if not texts:
            return []
        payload = {"model": config.model, "input": texts}
        response = httpx.post(
            _endpoint(config, "embedding"),
            headers=_headers(config),
            params=_params(config),
            json=payload,
            timeout=120.0,
        )
        if response.status_code in (400, 422) and len(texts) > 1:
            # The endpoint may only accept one input per request.
            return [AIProviderService.embed_sync(config, text) for text in texts]
        response.raise_for_status()
        data = response.json()
        rows = data.get("data") if isinstance(data, dict) else None
        if isinstance(rows, list) and len(rows) == len(texts):
            ordered = sorted(
                rows, key=lambda row: row.get("index", 0) if isinstance(row, dict) else 0
            )
            vectors = [
                row.get("embedding") if isinstance(row, dict) else None
                for row in ordered
            ]
            if all(isinstance(v, list) and v for v in vectors):
                if config.embedding_dimensions:
                    for vector in vectors:
                        if len(vector) != config.embedding_dimensions:
                            raise AIConfigError(
                                f"Embedding dimension mismatch: model returned {len(vector)}, "
                                f"but it is configured for {config.embedding_dimensions} dimensions."
                            )
                return vectors
        # Some custom endpoints only accept a single input.
        return [AIProviderService.embed_sync(config, text) for text in texts]

    @staticmethod
    def embed_sync(config: AIConfig, text: str) -> List[float]:
        payload = {"model": config.model, "input": [text]}
        response = httpx.post(
            _endpoint(config, "embedding"),
            headers=_headers(config),
            params=_params(config),
            json=payload,
            timeout=60.0,
        )
        response.raise_for_status()
        data = response.json()
        vector = _extract_vector(data)
        if not vector:
            raise AIConfigError("Embedding response is empty.")
        if config.embedding_dimensions and len(vector) != config.embedding_dimensions:
            raise AIConfigError(
                f"Embedding dimension mismatch: model returned {len(vector)}, "
                f"but it is configured for {config.embedding_dimensions} dimensions."
            )
        return vector

    @staticmethod
    async def complete(
        config: AIConfig,
        messages: List[Dict[str, str]],
        max_tokens: int = 512,
        temperature: float = 0.2,
    ) -> str:
        if config.adapter == "custom":
            payload: Dict[str, Any] = {
                "message": _simple_message(messages),
                "model": config.model,
            }
        else:
            payload = {
                "model": config.model,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
            }
        async with httpx.AsyncClient(timeout=90.0) as client:
            response = await client.post(
                _endpoint(config, "chat"),
                headers=_headers(config),
                params=_params(config),
                json=payload,
            )
            response.raise_for_status()
            data = response.json()
        return _extract_text(data)

    @staticmethod
    def complete_sync(
        config: AIConfig,
        messages: List[Dict[str, str]],
        max_tokens: int = 512,
        temperature: float = 0.2,
    ) -> str:
        if config.adapter == "custom":
            payload: Dict[str, Any] = {
                "message": _simple_message(messages),
                "model": config.model,
            }
        else:
            payload = {
                "model": config.model,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
            }
        response = httpx.post(
            _endpoint(config, "chat"),
            headers=_headers(config),
            params=_params(config),
            json=payload,
            timeout=90.0,
        )
        response.raise_for_status()
        data = response.json()
        return _extract_text(data)

    @staticmethod
    async def stream_chat(
        config: AIConfig,
        messages: List[Dict[str, str]],
        max_tokens: int = 512,
        temperature: float = 0.3,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        if config.adapter == "custom":
            # Simple custom APIs return a single JSON body, not SSE.
            text = await AIProviderService.complete(
                config, messages, max_tokens=max_tokens, temperature=temperature
            )
            if text:
                yield {"type": "token", "text": text}
            yield {"type": "done"}
            return

        payload = {
            "model": config.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True,
            "stream_options": {"include_usage": True},
        }
        async with httpx.AsyncClient(timeout=120.0) as client:
            async with client.stream(
                "POST",
                _endpoint(config, "chat"),
                headers=_headers(config),
                params=_params(config),
                json=payload,
            ) as response:
                if response.status_code >= 400:
                    body = (await response.aread()).decode("utf-8", "ignore")
                    raise AIConfigError(
                        f"Provider error {response.status_code}: {body[:300]}"
                    )

                async for line in response.aiter_lines():
                    if not line.startswith("data:"):
                        continue
                    raw = line[5:].strip()
                    if raw == "[DONE]":
                        yield {"type": "done"}
                        return
                    try:
                        data = json.loads(raw)
                    except Exception:
                        continue

                    choice = (data.get("choices") or [{}])[0]
                    delta = choice.get("delta") or {}
                    text = delta.get("content")
                    if text:
                        yield {"type": "token", "text": text}

                    usage = data.get("usage")
                    if usage:
                        yield {
                            "type": "usage",
                            "input": usage.get("prompt_tokens"),
                            "output": usage.get("completion_tokens"),
                        }

        yield {"type": "done"}
