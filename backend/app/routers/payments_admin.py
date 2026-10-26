"""Admin payment provider configuration."""

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.dependencies import get_db, require_admin_or_above, require_superadmin
from app.models.audit_log import AuditLog
from app.models.payment import PaymentOrder, PaymentProvider
from app.schemas.auth import CurrentAdmin
from app.services.payments.base import PaymentDriverError
from app.services.payments.registry import get_driver, metadata
from app.services.payments.service import MODES, PaymentService, PaymentServiceError
from app.utils.crypto import mask_secret

settings = get_settings()
logger = logging.getLogger("vidhya.payments")
router = APIRouter(prefix="/admin/payments", tags=["Admin Payments"])


class ProviderCreateRequest(BaseModel):
    driver: str
    mode: str
    display_name: Optional[str] = None
    credentials: Dict[str, Any] = {}


class ProviderUpdateRequest(BaseModel):
    display_name: Optional[str] = None
    credentials: Optional[Dict[str, Any]] = None
    clear_credentials: bool = False


class EnvironmentRequest(BaseModel):
    environment: str


class ActivateRequest(BaseModel):
    expire_pending: bool = False


def _meta_out(meta) -> Dict[str, Any]:
    return {
        "driver": meta.driver,
        "name": meta.name,
        "tagline": meta.tagline,
        "brand_slug": meta.brand_slug,
        "brand_color": meta.brand_color,
        "docs_url": meta.docs_url,
        "capabilities": list(meta.capabilities),
        "webhook_events": list(meta.webhook_events),
        "webhook_notes": meta.webhook_notes,
        "modes": list(meta.modes),
        "fields": [
            {
                "key": f.key,
                "label": f.label,
                "hint": f.hint,
                "secret": f.secret,
                "placeholder": f.placeholder,
                "default": f.default,
                "required": f.required,
            }
            for f in meta.fields
        ],
    }


def _provider_out(provider: PaymentProvider) -> Dict[str, Any]:
    driver = get_driver(provider.driver)
    fields = {f.key: "" for f in driver.meta.fields}
    configured = bool(provider.credentials_encrypted)
    if configured:
        try:
            creds = PaymentService.decrypt_credentials(provider)
            for f in driver.meta.fields:
                value = creds.get(f.key, "")
                if not value:
                    continue
                fields[f.key] = mask_secret(value) if f.secret else value
        except PaymentServiceError:
            fields = {k: "****" for k in fields}
    return {
        "id": str(provider.id),
        "driver": provider.driver,
        "mode": provider.mode,
        "display_name": provider.display_name,
        "is_active": provider.is_active,
        "configured": configured,
        "credential_preview": fields,
        "webhook_url": PaymentService.webhook_url(provider),
        "last_tested_at": provider.last_tested_at,
        "last_test_status": provider.last_test_status,
        "last_test_error": (
            (
                "Cashfree rejected the credentials. Use Payment Gateway sandbox or "
                "production keys from the same app — not Payouts or Secure ID keys."
                if provider.driver == "cashfree"
                else "Connection test failed. Check the provider credentials and try again."
            )
            if provider.last_test_error
            else None
        ),
    }


def _mode_credential_error(driver_name: str, mode: str, credentials: Dict[str, str]) -> Optional[str]:
    if driver_name == "razorpay":
        key_id = credentials.get("key_id", "")
        if mode == "production" and key_id.startswith("rzp_test_"):
            raise HTTPException(400, "That is a Razorpay test key. Use a live key for production.")
        if mode == "sandbox" and key_id.startswith("rzp_live_"):
            raise HTTPException(400, "That is a Razorpay live key. Use a test key for sandbox.")
    if (
        driver_name == "paytm"
        and mode == "production"
        and credentials.get("website", "").upper() == "WEBSTAGING"
    ):
        raise HTTPException(400, "Use your live Paytm website name, not WEBSTAGING.")
    if driver_name == "cashfree":
        app_id = credentials.get("app_id", "").upper()
        if mode == "production" and app_id.startswith("TEST"):
            raise HTTPException(
                400,
                "That is a Cashfree sandbox App ID. Use the production Payment Gateway keys.",
            )
        if mode == "sandbox" and app_id.startswith("PROD"):
            raise HTTPException(
                400,
                "That is a Cashfree production App ID. Use the sandbox Payment Gateway keys.",
            )
    return None


async def _load_provider(db: AsyncSession, provider_id: str) -> PaymentProvider:
    try:
        uid = uuid.UUID(provider_id)
    except ValueError:
        raise HTTPException(404, "Provider not found.")
    provider = (
        await db.execute(select(PaymentProvider).where(PaymentProvider.id == uid))
    ).scalar_one_or_none()
    if not provider:
        raise HTTPException(404, "Provider not found.")
    return provider


@router.get("/overview")
async def payment_overview(
    current_admin: CurrentAdmin = Depends(require_admin_or_above),
    db: AsyncSession = Depends(get_db),
):
    providers = (
        await db.execute(select(PaymentProvider).order_by(PaymentProvider.created_at))
    ).scalars().all()
    return {
        "environment": await PaymentService.get_environment(db),
        "demo_allowed": settings.payments_demo_allowed,
        "modes": list(MODES),
        "catalog": [_meta_out(m) for m in metadata()],
        "providers": [_provider_out(p) for p in providers],
    }


@router.post("/providers", status_code=status.HTTP_201_CREATED)
async def create_provider(
    payload: ProviderCreateRequest,
    current_admin: CurrentAdmin = Depends(require_superadmin),
    db: AsyncSession = Depends(get_db),
):
    try:
        driver = get_driver(payload.driver)
    except ValueError:
        raise HTTPException(400, "Unknown payment provider.")
    if payload.mode not in driver.meta.modes or payload.mode not in MODES:
        raise HTTPException(400, f"{driver.meta.name} does not support {payload.mode} mode.")
    if payload.mode == "demo" and not settings.payments_demo_allowed:
        raise HTTPException(400, "Demo mode is disabled in production.")

    existing = (
        await db.execute(
            select(PaymentProvider).where(
                PaymentProvider.driver == payload.driver,
                PaymentProvider.mode == payload.mode,
            )
        )
    ).scalar_one_or_none()
    if existing:
        raise HTTPException(409, "This provider is already configured for that mode.")

    credentials = driver.normalize_credentials(payload.credentials or {})
    missing = driver.validate_credentials(credentials)
    if missing:
        raise HTTPException(400, f"Missing: {', '.join(missing)}.")
    _mode_credential_error(payload.driver, payload.mode, credentials)
    try:
        encrypted = (
            PaymentService.encrypt_credentials(credentials)
            if credentials
            else None
        )
    except RuntimeError as exc:
        raise HTTPException(500, str(exc))

    provider = PaymentProvider(
        driver=payload.driver,
        mode=payload.mode,
        display_name=payload.display_name or driver.meta.name,
        credentials_encrypted=encrypted,
        is_active=False,
    )
    db.add(provider)
    db.add(
        AuditLog(
            admin_id=current_admin.id,
            action="payment.provider_created",
            resource_type="payment_provider",
            details={"driver": payload.driver, "mode": payload.mode},
        )
    )
    await db.commit()
    await db.refresh(provider)
    return _provider_out(provider)


@router.put("/providers/{provider_id}")
async def update_provider(
    provider_id: str,
    payload: ProviderUpdateRequest,
    current_admin: CurrentAdmin = Depends(require_superadmin),
    db: AsyncSession = Depends(get_db),
):
    provider = await _load_provider(db, provider_id)
    driver = get_driver(provider.driver)

    if payload.display_name:
        provider.display_name = payload.display_name.strip()[:120]

    if payload.clear_credentials:
        provider.credentials_encrypted = None
        provider.last_test_status = None
        provider.last_test_error = None
    elif payload.credentials is not None:
        try:
            current = PaymentService.decrypt_credentials(provider)
        except PaymentServiceError:
            current = {}
        merged = {**current}
        for key, value in payload.credentials.items():
            if value is None or str(value).strip() == "":
                continue
            merged[key] = str(value).strip()
        normalized = driver.normalize_credentials(merged)
        missing = driver.validate_credentials(normalized)
        if missing:
            raise HTTPException(400, f"Missing: {', '.join(missing)}.")
        _mode_credential_error(provider.driver, provider.mode, normalized)
        try:
            provider.credentials_encrypted = PaymentService.encrypt_credentials(normalized)
        except RuntimeError as exc:
            raise HTTPException(500, str(exc))
        provider.last_test_status = None
        provider.last_test_error = None

    db.add(
        AuditLog(
            admin_id=current_admin.id,
            action="payment.provider_updated",
            resource_type="payment_provider",
            resource_id=provider.id,
            details={"driver": provider.driver, "mode": provider.mode},
        )
    )
    await db.commit()
    await db.refresh(provider)
    return _provider_out(provider)


@router.delete("/providers/{provider_id}")
async def delete_provider(
    provider_id: str,
    current_admin: CurrentAdmin = Depends(require_superadmin),
    db: AsyncSession = Depends(get_db),
):
    provider = await _load_provider(db, provider_id)
    if provider.is_active:
        raise HTTPException(400, "Deactivate or switch providers before deleting this one.")
    orders = (
        await db.execute(
            select(func.count(PaymentOrder.id)).where(
                PaymentOrder.provider_id == provider.id
            )
        )
    ).scalar() or 0
    if orders:
        raise HTTPException(400, "This provider has payment history and cannot be deleted.")

    db.add(
        AuditLog(
            admin_id=current_admin.id,
            action="payment.provider_deleted",
            resource_type="payment_provider",
            details={"driver": provider.driver, "mode": provider.mode},
        )
    )
    await db.delete(provider)
    await db.commit()
    return {"status": "deleted"}


@router.post("/providers/{provider_id}/deactivate")
async def deactivate_provider(
    provider_id: str,
    current_admin: CurrentAdmin = Depends(require_superadmin),
    db: AsyncSession = Depends(get_db),
):
    provider = await _load_provider(db, provider_id)
    if not provider.is_active:
        return _provider_out(provider)

    provider.is_active = False
    db.add(
        AuditLog(
            admin_id=current_admin.id,
            action="payment.provider_deactivated",
            resource_type="payment_provider",
            resource_id=provider.id,
            details={"driver": provider.driver, "mode": provider.mode},
        )
    )
    await db.commit()
    await db.refresh(provider)
    return _provider_out(provider)


@router.post("/providers/{provider_id}/test")
async def test_provider(
    provider_id: str,
    current_admin: CurrentAdmin = Depends(require_superadmin),
    db: AsyncSession = Depends(get_db),
):
    provider = await _load_provider(db, provider_id)
    driver = get_driver(provider.driver)
    try:
        credentials = PaymentService.decrypt_credentials(provider)
        message = await driver.test_credentials(
            credentials=credentials, mode=provider.mode
        )
        provider.last_test_status = "ok"
        provider.last_test_error = None
        provider.last_tested_at = datetime.now(timezone.utc)
        await db.commit()
        return {"status": "ok", "message": message}
    except (PaymentDriverError, PaymentServiceError) as exc:
        logger.warning(
            "payment.test.failed provider=%s driver=%s mode=%s: %s",
            provider.id,
            provider.driver,
            provider.mode,
            exc,
        )
        detail = (
            getattr(exc, "safe_message", None)
            or "Connection test failed. Check the provider credentials and try again."
        )
        provider.last_test_status = "failed"
        provider.last_test_error = detail
        provider.last_tested_at = datetime.now(timezone.utc)
        await db.commit()
        raise HTTPException(400, detail)


@router.post("/providers/{provider_id}/activate")
async def activate_provider(
    provider_id: str,
    payload: ActivateRequest = ActivateRequest(),
    current_admin: CurrentAdmin = Depends(require_superadmin),
    db: AsyncSession = Depends(get_db),
):
    provider = await _load_provider(db, provider_id)
    driver = get_driver(provider.driver)

    credentials = PaymentService.decrypt_credentials(provider)
    missing = driver.validate_credentials(credentials)
    if missing:
        raise HTTPException(400, f"Missing: {', '.join(missing)}.")
    try:
        await driver.test_credentials(credentials=credentials, mode=provider.mode)
        provider.last_test_status = "ok"
        provider.last_test_error = None
        provider.last_tested_at = datetime.now(timezone.utc)
    except (PaymentDriverError, PaymentServiceError) as exc:
        logger.warning(
            "payment.activate.test_failed provider=%s driver=%s mode=%s: %s",
            provider.id,
            provider.driver,
            provider.mode,
            exc,
        )
        detail = (
            getattr(exc, "safe_message", None)
            or "Connection test failed. Check the provider credentials and try again."
        )
        provider.last_test_status = "failed"
        provider.last_test_error = detail
        await db.commit()
        raise HTTPException(400, detail)

    pending = (
        await db.execute(
            select(func.count(PaymentOrder.id)).where(
                PaymentOrder.mode == provider.mode,
                PaymentOrder.status.in_(("created", "pending")),
            )
        )
    ).scalar() or 0
    if pending and not payload.expire_pending:
        await db.commit()
        raise HTTPException(
            409,
            f"{pending} payment(s) are still pending in {provider.mode} mode. "
            "Wait for them or expire them before switching providers.",
        )
    if pending and payload.expire_pending:
        await db.execute(
            update(PaymentOrder)
            .where(
                PaymentOrder.mode == provider.mode,
                PaymentOrder.status.in_(("created", "pending")),
            )
            .values(status="expired", failure_reason="Expired by an admin provider switch.")
        )

    await db.execute(
        update(PaymentProvider)
        .where(PaymentProvider.mode == provider.mode)
        .values(is_active=False)
    )
    provider.is_active = True
    db.add(
        AuditLog(
            admin_id=current_admin.id,
            action="payment.provider_activated",
            resource_type="payment_provider",
            resource_id=provider.id,
            details={
                "driver": provider.driver,
                "mode": provider.mode,
                "expired_pending": pending if payload.expire_pending else 0,
            },
        )
    )
    await db.commit()
    await db.refresh(provider)
    return _provider_out(provider)


@router.get("/environment")
async def get_environment(
    current_admin: CurrentAdmin = Depends(require_admin_or_above),
    db: AsyncSession = Depends(get_db),
):
    return {
        "environment": await PaymentService.get_environment(db),
        "demo_allowed": settings.payments_demo_allowed,
        "modes": list(MODES),
    }


@router.put("/environment")
async def set_environment(
    payload: EnvironmentRequest,
    current_admin: CurrentAdmin = Depends(require_superadmin),
    db: AsyncSession = Depends(get_db),
):
    mode = await PaymentService.set_environment(db, payload.environment)
    db.add(
        AuditLog(
            admin_id=current_admin.id,
            action="payment.environment_changed",
            resource_type="platform_setting",
            details={"environment": mode},
        )
    )
    await db.commit()
    return {"environment": mode}
