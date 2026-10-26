"""
Vidhya AI — admin provider management.

  ai_chat_models      — several may be active; one is the default
  ai_embedding_models — exactly one active (unique partial index)

Keys are encrypted at rest, masked in every response, and adding a provider
requires a successful live test.
"""

import logging
import uuid
from typing import Any, Dict, List, Optional

import httpx
import redis.asyncio as aioredis
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import get_settings
from app.dependencies import (
    get_db,
    get_redis_client,
    require_admin_or_above,
    require_superadmin,
)
from app.models.ai_chat_model import AIChatModel
from app.models.ai_embedding_model import AIEmbeddingModel
from app.models.ai_provider import AIProvider
from app.models.audit_log import AuditLog
from app.models.chunk import DocumentChunk
from app.models.document import Document
from app.models.plan import Plan
from app.models.platform_setting import PlatformSetting
from app.schemas.auth import CurrentAdmin
from app.services.ai_providers import AIConfig, AIProviderService
from app.services.prompts import (
    DEFAULT_SYSTEM_PROMPT,
    SYSTEM_PROMPT_MAX_CHARS,
    SYSTEM_PROMPT_MAX_WORDS,
    SystemPromptError,
    clean_system_prompt,
)
from app.utils.crypto import decrypt_secret, encrypt_secret, mask_secret

settings = get_settings()
logger = logging.getLogger("vidhya.ai_admin")
router = APIRouter(prefix="/admin/ai", tags=["Admin AI"])



class ProviderTestRequest(BaseModel):
    adapter: str = "openai_compatible"
    base_url: str
    chat_url: Optional[str] = None
    embeddings_url: Optional[str] = None
    models_url: Optional[str] = None
    auth_type: str = "bearer"
    api_key: Optional[str] = None
    auth_key_name: Optional[str] = None
    auth_username: Optional[str] = None
    model: str
    kind: str = "chat"
    expected_dimensions: Optional[int] = None


class RemoteModelsRequest(BaseModel):
    adapter: str = "openai_compatible"
    base_url: str
    models_url: Optional[str] = None
    auth_type: str = "bearer"
    api_key: Optional[str] = None
    auth_key_name: Optional[str] = None
    auth_username: Optional[str] = None


class ProviderCreateRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=80)
    adapter: str = "openai_compatible"
    base_url: str
    chat_url: Optional[str] = None
    embeddings_url: Optional[str] = None
    models_url: Optional[str] = None
    auth_type: str = "bearer"
    auth_key_name: Optional[str] = None
    auth_username: Optional[str] = None
    api_key: Optional[str] = None
    test_model: str
    test_kind: str = "chat"
    test_dimensions: Optional[int] = None
    test_context_window: int = 32000
    test_max_output_tokens: int = 1024


class ProviderUpdateRequest(BaseModel):
    name: Optional[str] = Field(None, min_length=2, max_length=80)
    adapter: Optional[str] = None
    base_url: Optional[str] = None
    chat_url: Optional[str] = None
    embeddings_url: Optional[str] = None
    models_url: Optional[str] = None
    auth_type: Optional[str] = None
    auth_key_name: Optional[str] = None
    auth_username: Optional[str] = None
    api_key: Optional[str] = None
    clear_key: bool = False
    is_active: Optional[bool] = None


class ModelCreateRequest(BaseModel):
    name: str
    display_name: str
    kind: str  # chat | embedding
    context_window: int = 32000
    max_output_tokens: int = 1024
    embedding_dimensions: Optional[int] = None
    system_prompt: Optional[str] = None


class SetDefaultRequest(BaseModel):
    confirm_reindex: bool = False


class ModelUpdateRequest(BaseModel):
    display_name: Optional[str] = None
    context_window: Optional[int] = None
    max_output_tokens: Optional[int] = None
    embedding_dimensions: Optional[int] = None
    system_prompt: Optional[str] = None
    is_active: Optional[bool] = None



def _model_out(model, kind: str) -> Dict[str, Any]:
    if kind == "chat":
        return {
            "id": str(model.id),
            "provider_id": str(model.provider_id),
            "name": model.name,
            "display_name": model.display_name,
            "kind": "chat",
            "context_window": model.context_window,
            "max_output_tokens": model.max_output_tokens,
            "embedding_dimensions": None,
            "system_prompt": model.system_prompt,
            "is_default": model.is_default,
            "is_active": model.is_active,
        }
    return {
        "id": str(model.id),
        "provider_id": str(model.provider_id),
        "name": model.name,
        "display_name": model.display_name,
        "kind": "embedding",
        "context_window": 0,
        "max_output_tokens": 0,
        "embedding_dimensions": model.embedding_dimensions,
        "system_prompt": None,
        "is_default": model.is_active,
        "is_active": model.is_active,
    }


async def _find_model(db: AsyncSession, model_id: str):
    try:
        uid = uuid.UUID(model_id)
    except ValueError:
        return None, None
    chat = (
        await db.execute(select(AIChatModel).where(AIChatModel.id == uid))
    ).scalar_one_or_none()
    if chat:
        return chat, "chat"
    embedding = (
        await db.execute(
            select(AIEmbeddingModel).where(AIEmbeddingModel.id == uid)
        )
    ).scalar_one_or_none()
    if embedding:
        return embedding, "embedding"
    return None, None


def _provider_out(provider: AIProvider) -> Dict[str, Any]:
    masked = ""
    if provider.api_key_encrypted:
        try:
            masked = mask_secret(decrypt_secret(provider.api_key_encrypted))
        except Exception:
            masked = "****"
    models = [_model_out(m, "chat") for m in provider.chat_models]
    models += [_model_out(m, "embedding") for m in provider.embedding_models]
    return {
        "id": str(provider.id),
        "name": provider.name,
        "adapter": provider.adapter,
        "base_url": provider.base_url,
        "chat_url": provider.chat_url or "",
        "embeddings_url": provider.embeddings_url or "",
        "models_url": provider.models_url or "",
        "auth_type": provider.auth_type,
        "auth_key_name": provider.auth_key_name,
        "auth_username": provider.auth_username,
        "has_key": bool(provider.api_key_encrypted),
        "api_key_masked": masked,
        "is_active": provider.is_active,
        "models": models,
    }


def _ad_hoc_config(
    base_url: str,
    auth_type: str,
    api_key: Optional[str],
    auth_key_name: Optional[str],
    auth_username: Optional[str],
    model: str,
    kind: str,
    context_window: int = 0,
    max_output_tokens: int = 0,
    embedding_dimensions: Optional[int] = None,
    adapter: str = "openai_compatible",
    chat_url: Optional[str] = None,
    embeddings_url: Optional[str] = None,
    models_url: Optional[str] = None,
) -> AIConfig:
    return AIConfig(
        provider_id="",
        model_id="",
        provider_name="",
        adapter=adapter,
        base_url=base_url,
        chat_url=chat_url or "",
        embeddings_url=embeddings_url or "",
        models_url=models_url or "",
        auth_type=auth_type,
        auth_key_name=auth_key_name,
        auth_username=auth_username,
        api_key=api_key,
        api_key_encrypted=None,
        model=model,
        kind=kind,
        context_window=context_window,
        max_output_tokens=max_output_tokens,
        embedding_dimensions=embedding_dimensions,
    )



async def _promote_default_chat(
    db: AsyncSession, exclude_ids: set
) -> None:
    """Pick another active chat model when the default is deleted."""
    settings_row = await _get_defaults_row(db)
    stmt = (
        select(AIChatModel)
        .join(AIProvider, AIChatModel.provider_id == AIProvider.id)
        .where(
            AIChatModel.is_active.is_(True),
            AIProvider.is_active.is_(True),
        )
        .order_by(AIChatModel.created_at.asc())
    )
    if exclude_ids:
        stmt = stmt.where(AIChatModel.id.notin_(exclude_ids))
    candidate = (await db.execute(stmt)).scalars().first()
    if candidate:
        await db.execute(
            update(AIChatModel).values(is_default=False)
        )
        candidate.is_default = True
        settings_row.default_chat_model_id = candidate.id
    else:
        settings_row.default_chat_model_id = None


async def _plans_exceeding(
    db: AsyncSession, context_window: int, max_output_tokens: int
) -> List[Plan]:
    return (
        await db.execute(
            select(Plan).where(
                or_(
                    Plan.max_context_tokens + Plan.max_response_tokens + 128
                    > context_window,
                    Plan.max_response_tokens > max_output_tokens,
                )
            )
        )
    ).scalars().all()


def _plan_mismatch_error(plans: List[Plan]) -> HTTPException:
    names = ", ".join(p.display_name for p in plans)
    return HTTPException(
        400,
        f"This model's limits are too small for: {names}. "
        "Raise the context/output limits or reduce those plans first.",
    )

async def _get_defaults_row(db: AsyncSession) -> PlatformSetting:
    row = (
        await db.execute(select(PlatformSetting).where(PlatformSetting.id == 1))
    ).scalar_one_or_none()
    if not row:
        row = PlatformSetting(id=1, platform_mode="paid")
        db.add(row)
        await db.flush()
    return row


async def _active_embedding(db: AsyncSession) -> Optional[AIEmbeddingModel]:
    return (
        await db.execute(
            select(AIEmbeddingModel).where(AIEmbeddingModel.is_active.is_(True))
        )
    ).scalar_one_or_none()


async def _load_provider(db: AsyncSession, provider_id: str) -> AIProvider:
    try:
        uid = uuid.UUID(provider_id)
    except ValueError:
        raise HTTPException(404, "Provider not found.")
    provider = (
        await db.execute(
            select(AIProvider)
            .where(AIProvider.id == uid)
            .options(
                selectinload(AIProvider.chat_models),
                selectinload(AIProvider.embedding_models),
            )
        )
    ).scalar_one_or_none()
    if not provider:
        raise HTTPException(404, "Provider not found.")
    return provider



@router.get("/providers", status_code=status.HTTP_200_OK)
async def list_providers(
    current_admin: CurrentAdmin = Depends(require_admin_or_above),
    db: AsyncSession = Depends(get_db),
):
    providers = (
        await db.execute(
            select(AIProvider)
            .options(
                selectinload(AIProvider.chat_models),
                selectinload(AIProvider.embedding_models),
            )
            .order_by(AIProvider.created_at.asc())
        )
    ).scalars().all()
    return [_provider_out(p) for p in providers]


@router.post("/providers", status_code=status.HTTP_201_CREATED)
async def create_provider(
    payload: ProviderCreateRequest,
    current_admin: CurrentAdmin = Depends(require_superadmin),
    db: AsyncSession = Depends(get_db),
    redis: aioredis.Redis = Depends(get_redis_client),
):
    if (
        await db.execute(select(AIProvider).where(AIProvider.name == payload.name))
    ).scalar_one_or_none():
        raise HTTPException(409, "A provider with that name already exists.")
    if payload.test_kind not in ("chat", "embedding"):
        raise HTTPException(400, "test_kind must be chat or embedding.")
    if payload.test_kind == "chat" and payload.test_max_output_tokens >= payload.test_context_window:
        raise HTTPException(
            400, "Max output tokens must be less than the context window."
        )
    if payload.adapter not in ("openai_compatible", "custom"):
        raise HTTPException(400, "adapter must be openai_compatible or custom.")
    if payload.adapter == "custom":
        needed = ["models_url"]
        needed.append("chat_url" if payload.test_kind == "chat" else "embeddings_url")
        missing = [name for name in needed if not getattr(payload, name)]
        if missing:
            raise HTTPException(
                400,
                "The custom adapter needs: " + ", ".join(missing) + ".",
            )

    config = _ad_hoc_config(
        payload.base_url,
        payload.auth_type,
        payload.api_key,
        payload.auth_key_name,
        payload.auth_username,
        payload.test_model,
        payload.test_kind,
        embedding_dimensions=(
            payload.test_dimensions if payload.test_kind == "embedding" else None
        ),
        adapter=payload.adapter,
        chat_url=payload.chat_url,
        embeddings_url=payload.embeddings_url,
        models_url=payload.models_url,
    )
    try:
        test_result = (
            await AIProviderService.test_embedding(config)
            if payload.test_kind == "embedding"
            else await AIProviderService.test_chat(config)
        )
    except Exception:
        logger.exception("ai.provider.test_failed")
        raise HTTPException(
            400,
            "Provider test failed. Check the endpoint, model name and API key.",
        )

    provider = AIProvider(
        name=payload.name,
        adapter=payload.adapter,
        base_url=payload.base_url.rstrip("/"),
        chat_url=payload.chat_url or None,
        embeddings_url=payload.embeddings_url or None,
        models_url=payload.models_url or None,
        auth_type=payload.auth_type,
        auth_key_name=payload.auth_key_name,
        auth_username=payload.auth_username,
        api_key_encrypted=(
            encrypt_secret(payload.api_key) if payload.api_key else None
        ),
        is_active=True,
        created_by=current_admin.id,
    )
    db.add(provider)
    await db.flush()

    defaults_row = await _get_defaults_row(db)

    if payload.test_kind == "chat":
        if defaults_row.default_chat_model_id is None:
            oversized = await _plans_exceeding(
                db, payload.test_context_window, payload.test_max_output_tokens
            )
            if oversized:
                raise _plan_mismatch_error(oversized)
        model = AIChatModel(
            provider_id=provider.id,
            name=payload.test_model,
            display_name=payload.test_model,
            context_window=payload.test_context_window,
            max_output_tokens=payload.test_max_output_tokens,
            is_active=True,
        )
        db.add(model)
        await db.flush()
        if defaults_row.default_chat_model_id is None:
            defaults_row.default_chat_model_id = model.id
            model.is_default = True
    else:
        dimensions = test_result.get("dimensions")
        schema_dimensions = defaults_row.embedding_dimensions
        active = await _active_embedding(db)
        make_active = active is None

        if make_active and dimensions != schema_dimensions:
            raise HTTPException(
                400,
                f"The embedding model returns {dimensions} dimensions, but the "
                f"database vector column is {schema_dimensions}. Change the schema "
                "dimension and re-index before using it.",
            )

        model = AIEmbeddingModel(
            provider_id=provider.id,
            name=payload.test_model,
            display_name=payload.test_model,
            embedding_dimensions=dimensions,
            is_active=make_active,
        )
        db.add(model)
        await db.flush()

    db.add(
        AuditLog(
            admin_id=current_admin.id,
            action="ai.provider_created",
            resource_type="ai_provider",
            resource_id=provider.id,
            details={"name": provider.name, "test_model": payload.test_model},
        )
    )
    await db.commit()
    await AIProviderService.invalidate(redis)
    provider = await _load_provider(db, str(provider.id))
    return _provider_out(provider)


@router.put("/providers/{provider_id}", status_code=status.HTTP_200_OK)
async def update_provider(
    provider_id: str,
    payload: ProviderUpdateRequest,
    current_admin: CurrentAdmin = Depends(require_superadmin),
    db: AsyncSession = Depends(get_db),
    redis: aioredis.Redis = Depends(get_redis_client),
):
    provider = await _load_provider(db, provider_id)
    data = payload.model_dump(exclude_unset=True)

    if data.get("is_active") is False:
        settings_row = await _get_defaults_row(db)
        chat_default = settings_row.default_chat_model_id
        active_embedding = await _active_embedding(db)
        if any(m.id == chat_default for m in provider.chat_models) or (
            active_embedding
            and any(m.id == active_embedding.id for m in provider.embedding_models)
        ):
            raise HTTPException(
                400,
                "This provider contains the default chat model or the active "
                "embedding model. Choose another first.",
            )

    if data.get("api_key"):
        provider.api_key_encrypted = encrypt_secret(data.pop("api_key"))
    else:
        data.pop("api_key", None)
    if data.pop("clear_key", False):
        provider.api_key_encrypted = None

    for key in (
        "name",
        "adapter",
        "base_url",
        "chat_url",
        "embeddings_url",
        "models_url",
        "auth_type",
        "auth_key_name",
        "auth_username",
        "is_active",
    ):
        if key in data and data[key] is not None:
            setattr(provider, key, data[key])
    if provider.base_url:
        provider.base_url = provider.base_url.rstrip("/")

    db.add(
        AuditLog(
            admin_id=current_admin.id,
            action="ai.provider_updated",
            resource_type="ai_provider",
            resource_id=provider.id,
            details={"fields": list(data.keys())},
        )
    )
    await db.commit()
    await AIProviderService.invalidate(redis)
    return _provider_out(provider)


@router.delete("/providers/{provider_id}", status_code=status.HTTP_200_OK)
async def delete_provider(
    provider_id: str,
    force: bool = False,
    current_admin: CurrentAdmin = Depends(require_superadmin),
    db: AsyncSession = Depends(get_db),
    redis: aioredis.Redis = Depends(get_redis_client),
):
    provider = await _load_provider(db, provider_id)
    settings_row = await _get_defaults_row(db)
    active_embedding = await _active_embedding(db)
    chat_ids = {m.id for m in provider.chat_models}
    embedding_ids = {m.id for m in provider.embedding_models}

    if settings_row.default_chat_model_id in chat_ids:
        if not force:
            raise HTTPException(
                400,
                "This provider contains the default chat model. Deleting it "
                "leaves chat unconfigured until you choose another default.",
            )
        settings_row.default_chat_model_id = None
        await _promote_default_chat(db, chat_ids)
    if active_embedding and active_embedding.id in embedding_ids:
        if not force:
            raise HTTPException(
                400,
                "This provider contains the active embedding model. Deleting it "
                "removes its vectors and disables document search.",
            )
    if (
        settings_row.reindex_status in ("queued", "running")
        and settings_row.reindex_target_model_id in embedding_ids
    ):
        if not force:
            raise HTTPException(
                409, "Cannot delete a provider while its model is being re-indexed."
            )
        settings_row.reindex_status = "failed"
        settings_row.reindex_error = "Provider deleted by an admin."
        settings_row.reindex_target_model_id = None

    if settings_row.reindex_target_model_id in embedding_ids:
        settings_row.reindex_target_model_id = None

    if embedding_ids:
        await db.execute(
            update(DocumentChunk)
            .where(DocumentChunk.embedding_model_id.in_(embedding_ids))
            .values(embedding=None, embedding_model_id=None)
        )

    await db.delete(provider)
    db.add(
        AuditLog(
            admin_id=current_admin.id,
            action="ai.provider_deleted",
            resource_type="ai_provider",
            resource_id=provider.id,
            details={"name": provider.name},
        )
    )
    await db.commit()
    await AIProviderService.invalidate(redis)
    return {"status": "deleted"}



@router.post("/providers/models/remote", status_code=status.HTTP_200_OK)
async def remote_models(
    payload: RemoteModelsRequest,
    current_admin: CurrentAdmin = Depends(require_superadmin),
):
    try:
        models = await AIProviderService.fetch_models(
            payload.base_url,
            payload.auth_type,
            payload.api_key,
            payload.auth_key_name,
            payload.auth_username,
            models_url=payload.models_url,
            adapter=payload.adapter,
        )
    except httpx.HTTPStatusError as exc:
        logger.warning("ai.models.discovery_failed status=%s", exc.response.status_code)
        if exc.response.status_code == 404:
            raise HTTPException(
                400,
                "This provider does not expose a model list. "
                "Type the model name manually instead.",
            )
        raise HTTPException(
            400,
            "Unable to load models. Check the provider URL and API key.",
        )
    except Exception:
        logger.exception("ai.models.discovery_failed")
        raise HTTPException(
            400,
            "Unable to load models. Check the provider URL and API key.",
        )
    return {"models": models}


@router.post("/providers/test", status_code=status.HTTP_200_OK)
async def test_provider(
    payload: ProviderTestRequest,
    current_admin: CurrentAdmin = Depends(require_superadmin),
):
    config = _ad_hoc_config(
        payload.base_url,
        payload.auth_type,
        payload.api_key,
        payload.auth_key_name,
        payload.auth_username,
        payload.model,
        payload.kind,
        embedding_dimensions=(
            payload.expected_dimensions if payload.kind == "embedding" else None
        ),
        adapter=payload.adapter,
        chat_url=payload.chat_url,
        embeddings_url=payload.embeddings_url,
        models_url=payload.models_url,
    )
    try:
        if payload.kind == "embedding":
            return await AIProviderService.test_embedding(config)
        return await AIProviderService.test_chat(config)
    except Exception:
        logger.exception("ai.provider.test_failed")
        raise HTTPException(
            400,
            "Provider test failed. Check the endpoint, model name and API key.",
        )


@router.post(
    "/providers/{provider_id}/test", status_code=status.HTTP_200_OK
)
async def test_saved_provider(
    provider_id: str,
    model: str,
    kind: str = "chat",
    current_admin: CurrentAdmin = Depends(require_superadmin),
    db: AsyncSession = Depends(get_db),
):
    provider = await _load_provider(db, provider_id)

    expected_dimensions = None
    if kind == "embedding":
        stored = next(
            (m for m in provider.embedding_models if m.name == model), None
        )
        expected_dimensions = stored.embedding_dimensions if stored else None

    config = _ad_hoc_config(
        provider.base_url,
        provider.auth_type,
        decrypt_secret(provider.api_key_encrypted)
        if provider.api_key_encrypted
        else None,
        provider.auth_key_name,
        provider.auth_username,
        model,
        kind,
        embedding_dimensions=expected_dimensions,
        adapter=provider.adapter,
        chat_url=provider.chat_url,
        embeddings_url=provider.embeddings_url,
        models_url=provider.models_url,
    )
    try:
        if kind == "embedding":
            return await AIProviderService.test_embedding(config)
        return await AIProviderService.test_chat(config)
    except Exception:
        logger.exception("ai.provider.test_failed")
        raise HTTPException(
            400,
            "Provider test failed. Check the endpoint, model name and API key.",
        )



@router.post(
    "/providers/{provider_id}/models", status_code=status.HTTP_201_CREATED
)
async def create_model(
    provider_id: str,
    payload: ModelCreateRequest,
    current_admin: CurrentAdmin = Depends(require_superadmin),
    db: AsyncSession = Depends(get_db),
    redis: aioredis.Redis = Depends(get_redis_client),
):
    provider = await _load_provider(db, provider_id)
    defaults_row = await _get_defaults_row(db)

    if payload.kind == "chat":
        if payload.embedding_dimensions is not None:
            raise HTTPException(400, "Chat models do not have embedding dimensions.")
        try:
            system_prompt = clean_system_prompt(payload.system_prompt or "")
        except SystemPromptError as exc:
            raise HTTPException(400, str(exc))
        if payload.max_output_tokens >= payload.context_window:
            raise HTTPException(
                400, "Max output tokens must be less than the context window."
            )
        if defaults_row.default_chat_model_id is None:
            oversized = await _plans_exceeding(
                db, payload.context_window, payload.max_output_tokens
            )
            if oversized:
                raise _plan_mismatch_error(oversized)
        if (
            await db.execute(
                select(AIChatModel).where(
                    AIChatModel.provider_id == provider.id,
                    func.lower(AIChatModel.name) == payload.name.strip().lower(),
                )
            )
        ).scalar_one_or_none():
            raise HTTPException(409, "That chat model already exists for this provider.")

        model = AIChatModel(
            provider_id=provider.id,
            name=payload.name,
            display_name=payload.display_name or payload.name,
            context_window=payload.context_window,
            max_output_tokens=payload.max_output_tokens,
            system_prompt=system_prompt,
            is_active=True,
        )
        db.add(model)
        await db.flush()

        if defaults_row.default_chat_model_id is None:
            defaults_row.default_chat_model_id = model.id
            model.is_default = True

        await db.commit()
        await AIProviderService.invalidate(redis)
        return _model_out(model, "chat")

    if payload.kind != "embedding":
        raise HTTPException(400, "kind must be chat or embedding.")
    if payload.system_prompt:
        raise HTTPException(400, "Embedding models do not use a system prompt.")
    if not payload.embedding_dimensions:
        raise HTTPException(400, "embedding_dimensions is required.")

    if (
        await db.execute(
            select(AIEmbeddingModel).where(
                AIEmbeddingModel.provider_id == provider.id,
                func.lower(AIEmbeddingModel.name) == payload.name.strip().lower(),
            )
        )
    ).scalar_one_or_none():
        raise HTTPException(
            409, "That embedding model already exists for this provider."
        )

    test_config = _ad_hoc_config(
        provider.base_url,
        provider.auth_type,
        decrypt_secret(provider.api_key_encrypted)
        if provider.api_key_encrypted
        else None,
        provider.auth_key_name,
        provider.auth_username,
        payload.name,
        "embedding",
        embedding_dimensions=payload.embedding_dimensions,
        adapter=provider.adapter,
        chat_url=provider.chat_url,
        embeddings_url=provider.embeddings_url,
        models_url=provider.models_url,
    )
    try:
        await AIProviderService.test_embedding(test_config)
    except Exception:
        logger.exception("ai.embedding.test_failed")
        raise HTTPException(
            400,
            "Embedding test failed. Check the model name, URL and API key. "
            f"The model must return exactly {payload.embedding_dimensions} dimensions.",
        )

    active = await _active_embedding(db)
    make_active = active is None
    if make_active and payload.embedding_dimensions != defaults_row.embedding_dimensions:
        raise HTTPException(
            400,
            f"The database vector column is {defaults_row.embedding_dimensions} "
            "dimensions; change it before activating this model.",
        )

    model = AIEmbeddingModel(
        provider_id=provider.id,
        name=payload.name,
        display_name=payload.display_name or payload.name,
        embedding_dimensions=payload.embedding_dimensions,
        is_active=make_active,
    )
    db.add(model)
    await db.commit()
    await AIProviderService.invalidate(redis)
    return _model_out(model, "embedding")


@router.put("/models/{model_id}", status_code=status.HTTP_200_OK)
async def update_model(
    model_id: str,
    payload: ModelUpdateRequest,
    current_admin: CurrentAdmin = Depends(require_superadmin),
    db: AsyncSession = Depends(get_db),
    redis: aioredis.Redis = Depends(get_redis_client),
):
    model, kind = await _find_model(db, model_id)
    if not model:
        raise HTTPException(404, "Model not found.")

    data = payload.model_dump(exclude_unset=True)

    if kind == "chat":
        if data.get("embedding_dimensions") is not None:
            raise HTTPException(400, "Chat models do not have embedding dimensions.")
        data.pop("embedding_dimensions", None)
        if "system_prompt" in data:
            try:
                data["system_prompt"] = clean_system_prompt(
                    data["system_prompt"] or ""
                )
            except SystemPromptError as exc:
                raise HTTPException(400, str(exc))

        new_window = data.get("context_window", model.context_window)
        new_output = data.get("max_output_tokens", model.max_output_tokens)
        if new_output >= new_window:
            raise HTTPException(
                400, "Max output tokens must be less than the context window."
            )

        settings_row = await _get_defaults_row(db)
        if data.get("is_active") is False and settings_row.default_chat_model_id == model.id:
            raise HTTPException(
                400,
                "This is the default chat model. Choose another default before disabling it.",
            )
        if model.is_default:
            oversized = await _plans_exceeding(db, new_window, new_output)
            if oversized:
                raise _plan_mismatch_error(oversized)
    else:
        if data.get("system_prompt") is not None:
            raise HTTPException(400, "Embedding models do not use a system prompt.")
        data.pop("system_prompt", None)
        if data.get("is_active") is not None:
            raise HTTPException(
                400,
                "Use Activate to choose the active embedding model.",
            )
        new_dimensions = data.get("embedding_dimensions", model.embedding_dimensions)
        if new_dimensions != model.embedding_dimensions:
            if model.is_active:
                settings_row = await _get_defaults_row(db)
                if new_dimensions != settings_row.embedding_dimensions:
                    raise HTTPException(
                        400,
                        f"The active embedding model must return "
                        f"{settings_row.embedding_dimensions} dimensions.",
                    )
            provider = await _load_provider(db, str(model.provider_id))
            test_config = _ad_hoc_config(
                provider.base_url,
                provider.auth_type,
                decrypt_secret(provider.api_key_encrypted)
                if provider.api_key_encrypted
                else None,
                provider.auth_key_name,
                provider.auth_username,
                model.name,
                "embedding",
                embedding_dimensions=new_dimensions,
                adapter=provider.adapter,
                chat_url=provider.chat_url,
                embeddings_url=provider.embeddings_url,
                models_url=provider.models_url,
            )
            try:
                await AIProviderService.test_embedding(test_config)
            except Exception:
                logger.exception("ai.embedding.test_failed")
                raise HTTPException(
                    400,
                    "Embedding test failed. Check the model name, URL and API key.",
                )

    allowed = (
        {
            "display_name",
            "context_window",
            "max_output_tokens",
            "system_prompt",
            "is_active",
        }
        if kind == "chat"
        else {"display_name", "embedding_dimensions"}
    )
    for key, value in data.items():
        if key in allowed and value is not None:
            setattr(model, key, value)

    await db.commit()
    await AIProviderService.invalidate(redis)
    return _model_out(model, kind)


@router.delete("/models/{model_id}", status_code=status.HTTP_200_OK)
async def delete_model(
    model_id: str,
    force: bool = False,
    current_admin: CurrentAdmin = Depends(require_superadmin),
    db: AsyncSession = Depends(get_db),
    redis: aioredis.Redis = Depends(get_redis_client),
):
    model, kind = await _find_model(db, model_id)
    if not model:
        raise HTTPException(404, "Model not found.")

    settings_row = await _get_defaults_row(db)
    active_embedding = await _active_embedding(db)

    if kind == "chat" and settings_row.default_chat_model_id == model.id:
        if not force:
            raise HTTPException(
                400,
                "This is the default chat model. Deleting it leaves chat "
                "unconfigured until you choose another default.",
            )
        settings_row.default_chat_model_id = None
        await _promote_default_chat(db, {model.id})
    if kind == "embedding" and active_embedding and active_embedding.id == model.id:
        if not force:
            raise HTTPException(
                400,
                "This is the active embedding model. Deleting it removes its "
                "vectors and disables document search until another model is active.",
            )
    if (
        kind == "embedding"
        and settings_row.reindex_status in ("queued", "running")
        and settings_row.reindex_target_model_id == model.id
    ):
        if not force:
            raise HTTPException(
                409, "Cannot delete the model while it is being re-indexed."
            )
        settings_row.reindex_status = "failed"
        settings_row.reindex_error = "Model deleted by an admin."
        settings_row.reindex_target_model_id = None
    if settings_row.reindex_target_model_id == model.id:
        settings_row.reindex_target_model_id = None

    if kind == "embedding":
        # The vectors are unusable once their model is gone.
        await db.execute(
            update(DocumentChunk)
            .where(DocumentChunk.embedding_model_id == model.id)
            .values(embedding=None, embedding_model_id=None)
        )

    await db.delete(model)
    await db.commit()
    await AIProviderService.invalidate(redis)
    return {"status": "deleted"}


@router.post("/models/{model_id}/default", status_code=status.HTTP_200_OK)
async def set_default_model(
    model_id: str,
    payload: SetDefaultRequest = SetDefaultRequest(),
    current_admin: CurrentAdmin = Depends(require_superadmin),
    db: AsyncSession = Depends(get_db),
    redis: aioredis.Redis = Depends(get_redis_client),
):
    model, kind = await _find_model(db, model_id)
    if not model:
        raise HTTPException(404, "Model not found.")
    settings_row = await _get_defaults_row(db)

    if kind == "chat":
        if not model.is_active:
            raise HTTPException(400, "Activate the model before making it the default.")
        if model.max_output_tokens >= model.context_window:
            raise HTTPException(
                400, "Max output tokens must be less than the context window."
            )
        oversized = await _plans_exceeding(
            db, model.context_window, model.max_output_tokens
        )
        if oversized:
            raise _plan_mismatch_error(oversized)

        await db.execute(
            update(AIChatModel)
            .where(AIChatModel.is_default.is_(True))
            .values(is_default=False)
        )
        model.is_default = True
        settings_row.default_chat_model_id = model.id

        db.add(
            AuditLog(
                admin_id=current_admin.id,
                action="ai.default_chat_model_changed",
                resource_type="ai_chat_model",
                resource_id=model.id,
                details={"model": model.name},
            )
        )
        await db.commit()
        await AIProviderService.invalidate(redis)
        return {"status": "default_set", "model": _model_out(model, kind)}

    if model.embedding_dimensions != settings_row.embedding_dimensions:
        raise HTTPException(
            400,
            f"This embedding model returns {model.embedding_dimensions} dimensions, "
            f"but the database vector column is {settings_row.embedding_dimensions}. "
            "Changing the dimension requires a schema migration and a full re-index.",
        )

    active = await _active_embedding(db)
    if active and active.id == model.id:
        return {"status": "default_set", "model": _model_out(model, kind)}

    if settings_row.reindex_status in ("queued", "running"):
        raise HTTPException(
            409, "A re-index job is already running. Wait for it to finish."
        )

    doc_count = (
        await db.execute(
            select(func.count(Document.id)).where(Document.is_active.is_(True))
        )
    ).scalar() or 0

    if doc_count > 0 and not payload.confirm_reindex:
        return {
            "status": "reindex_required",
            "documents": doc_count,
            "model": _model_out(model, kind),
        }

    # Enforce one active embedding model: deactivate the rest first.
    await db.execute(update(AIEmbeddingModel).values(is_active=False))
    model.is_active = True

    queue_reindex = doc_count > 0
    if queue_reindex:
        settings_row.reindex_status = "queued"
        settings_row.reindex_target_model_id = model.id
        settings_row.reindex_total = doc_count
        settings_row.reindex_done = 0
        settings_row.reindex_failed = 0
        settings_row.reindex_started_at = None
        settings_row.reindex_completed_at = None
        settings_row.reindex_error = None
    else:
        settings_row.reindex_status = "idle"
        settings_row.reindex_target_model_id = None
        settings_row.reindex_total = 0
        settings_row.reindex_done = 0
        settings_row.reindex_failed = 0
        settings_row.reindex_started_at = None
        settings_row.reindex_completed_at = None
        settings_row.reindex_error = None

    db.add(
        AuditLog(
            admin_id=current_admin.id,
            action="ai.active_embedding_changed",
            resource_type="ai_embedding_model",
            resource_id=model.id,
            details={
                "model": model.name,
                "reindex_queued": queue_reindex,
                "documents": doc_count,
            },
        )
    )
    await db.commit()
    await AIProviderService.invalidate(redis)

    if queue_reindex:
        try:
            from app.workers.reindex_embeddings import reindex_embeddings

            reindex_embeddings.delay(str(model.id))
        except Exception as e:
            settings_row.reindex_status = "failed"
            settings_row.reindex_error = f"Could not queue the job: {e}"
            await db.commit()
            raise HTTPException(
                503,
                "The embedding model changed, but the re-index job could not be queued. "
                "Use Re-index now to retry.",
            )
        return {
            "status": "queued",
            "documents": doc_count,
            "model": _model_out(model, kind),
        }

    return {"status": "default_set", "model": _model_out(model, kind)}



def _reindex_payload(
    row: PlatformSetting, target: Optional[AIEmbeddingModel]
) -> Dict[str, Any]:
    return {
        "status": row.reindex_status or "idle",
        "total": row.reindex_total,
        "done": row.reindex_done,
        "failed": row.reindex_failed,
        "target_model": target.display_name if target else None,
        "target_model_id": str(target.id) if target else None,
        "started_at": row.reindex_started_at.isoformat()
        if row.reindex_started_at
        else None,
        "completed_at": row.reindex_completed_at.isoformat()
        if row.reindex_completed_at
        else None,
        "error": row.reindex_error,
    }



async def _embedding_stats(
    db: AsyncSession, model: Optional[AIEmbeddingModel]
) -> Dict[str, int]:
    documents_total = (
        await db.execute(
            select(func.count(Document.id)).where(Document.is_active.is_(True))
        )
    ).scalar() or 0
    if not model:
        return {
            "documents_total": documents_total,
            "documents_embedded": 0,
            "chunks_total": 0,
            "chunks_embedded": 0,
        }

    documents_embedded = (
        await db.execute(
            select(func.count(func.distinct(DocumentChunk.document_id)))
            .join(Document, Document.id == DocumentChunk.document_id)
            .where(
                Document.is_active.is_(True),
                DocumentChunk.embedding_model_id == model.id,
            )
        )
    ).scalar() or 0
    chunks_embedded = (
        await db.execute(
            select(func.count(DocumentChunk.id)).where(
                DocumentChunk.embedding_model_id == model.id
            )
        )
    ).scalar() or 0
    chunks_total = (
        await db.execute(
            select(func.count(DocumentChunk.id))
            .join(Document, Document.id == DocumentChunk.document_id)
            .where(Document.is_active.is_(True))
        )
    ).scalar() or 0
    return {
        "documents_total": documents_total,
        "documents_embedded": documents_embedded,
        "chunks_total": chunks_total,
        "chunks_embedded": chunks_embedded,
    }


@router.get("/reindex/status", status_code=status.HTTP_200_OK)
async def get_reindex_status(
    current_admin: CurrentAdmin = Depends(require_admin_or_above),
    db: AsyncSession = Depends(get_db),
):
    row = await _get_defaults_row(db)
    target = None
    if row.reindex_target_model_id:
        target = (
            await db.execute(
                select(AIEmbeddingModel).where(
                    AIEmbeddingModel.id == row.reindex_target_model_id
                )
            )
        ).scalar_one_or_none()
    active = await _active_embedding(db)
    payload = _reindex_payload(row, target or active)
    payload.update(await _embedding_stats(db, active))
    return payload


@router.post("/reindex", status_code=status.HTTP_200_OK)
async def start_reindex(
    current_admin: CurrentAdmin = Depends(require_superadmin),
    db: AsyncSession = Depends(get_db),
    redis: aioredis.Redis = Depends(get_redis_client),
):
    row = await _get_defaults_row(db)
    if row.reindex_status in ("queued", "running"):
        raise HTTPException(409, "A re-index job is already running.")

    model = await _active_embedding(db)
    if not model:
        raise HTTPException(400, "Activate an embedding model first.")

    doc_count = (
        await db.execute(
            select(func.count(Document.id)).where(Document.is_active.is_(True))
        )
    ).scalar() or 0

    row.reindex_target_model_id = model.id
    row.reindex_total = doc_count
    row.reindex_done = 0
    row.reindex_failed = 0
    row.reindex_started_at = None
    row.reindex_completed_at = None
    row.reindex_error = None
    row.reindex_status = "queued" if doc_count else "completed"

    db.add(
        AuditLog(
            admin_id=current_admin.id,
            action="ai.reindex_started",
            resource_type="ai_embedding_model",
            resource_id=model.id,
            details={"documents": doc_count},
        )
    )
    await db.commit()
    await AIProviderService.invalidate(redis)

    if doc_count == 0:
        return _reindex_payload(row, model)

    try:
        from app.workers.reindex_embeddings import reindex_embeddings

        reindex_embeddings.delay(str(model.id))
    except Exception as e:
        row.reindex_status = "failed"
        row.reindex_error = f"Could not queue the job: {e}"
        await db.commit()
        raise HTTPException(503, "Could not queue the re-index job.")

    return _reindex_payload(row, model)


@router.get("/defaults", status_code=status.HTTP_200_OK)
async def get_defaults(
    current_admin: CurrentAdmin = Depends(require_admin_or_above),
    db: AsyncSession = Depends(get_db),
    redis: aioredis.Redis = Depends(get_redis_client),
):
    settings_row = await _get_defaults_row(db)
    result: Dict[str, Any] = {
        "vector_dimensions": settings_row.embedding_dimensions,
        "default_system_prompt": DEFAULT_SYSTEM_PROMPT,
        "system_prompt_max_chars": SYSTEM_PROMPT_MAX_CHARS,
        "system_prompt_max_words": SYSTEM_PROMPT_MAX_WORDS,
    }
    for kind in ("chat", "embedding"):
        try:
            config = await AIProviderService.get_default(db, redis, kind)
            result[kind] = {
                "provider": config.provider_name,
                "model": config.model,
                "context_window": config.context_window,
                "max_output_tokens": config.max_output_tokens,
                "embedding_dimensions": config.embedding_dimensions,
                "system_prompt": config.system_prompt if kind == "chat" else None,
            }
            result[f"{kind}_error"] = None
        except Exception as exc:
            result[kind] = None
            result[f"{kind}_error"] = str(exc)
    return result
