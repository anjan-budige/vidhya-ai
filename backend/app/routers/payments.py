"""
Vidhya AI — public payment endpoints.

/initiate creates an order with the active provider for the configured
environment (demo / sandbox / production). Webhooks are signature-verified,
idempotent and credited once.
"""

import hashlib
import logging
import uuid
from datetime import datetime, timezone
from typing import List, Optional

import redis.asyncio as aioredis
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.dependencies import (
    get_current_user,
    get_db,
    get_redis_client,
    require_billing_enabled,
    require_superadmin,
)
from app.models.payment import PaymentEvent, PaymentOrder, PaymentProvider
from app.models.user import User
from app.schemas.auth import CurrentUser, CurrentAdmin
from app.schemas.payment import (
    AdminPaymentHistoryResponse,
    DemoCompleteRequest,
    PaymentHistoryResponse,
    PaymentInitiateRequest,
    PaymentInitiateResponse,
    PaymentVerifyResponse,
)
from app.services.payments.base import PaymentDriverError, SignatureError
from app.services.payments.pages import demo_checkout_page
from app.services.payments.registry import get_driver
from app.services.payments.service import (
    PAYMENT_START_FAILED,
    PaymentAmountError,
    PaymentService,
    PaymentServiceError,
    legacy_status,
)
from app.services.platform import PAID, PlatformConfigService

logger = logging.getLogger("vidhya.payments")
settings = get_settings()
router = APIRouter(prefix="/payments", tags=["Payments / Billing"])


@router.post(
    "/initiate",
    response_model=PaymentInitiateResponse,
    status_code=status.HTTP_201_CREATED,
)
async def initiate_payment(
    payload: PaymentInitiateRequest,
    request: Request,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    _billing_enabled: None = Depends(require_billing_enabled),
):
    user = (
        await db.execute(select(User).where(User.id == current_user.id))
    ).scalar_one()

    idempotency = (
        payload.idempotency_key or request.headers.get("Idempotency-Key") or None
    )
    try:
        order = await PaymentService.create_order(
            user=user,
            plan_id=payload.plan_id,
            idempotency_key=idempotency,
            db=db,
        )
    except PaymentServiceError as exc:
        logger.error("payment.start.service_error user=%s plan=%s: %s", user.id, payload.plan_id, exc)
        raise HTTPException(503, PAYMENT_START_FAILED)

    logger.info(
        "payment.initiated ref=%s user=%s plan=%s mode=%s provider=%s",
        order.order_ref,
        user.id,
        order.plan_name,
        order.mode,
        order.provider_driver,
    )
    return PaymentInitiateResponse(
        merchant_txn_id=order.order_ref,
        order_ref=order.order_ref,
        payment_url=order.payment_url or "",
        amount_inr=order.amount_paise,
        amount_paise=order.amount_paise,
        plan_name=order.plan_name or "Plan",
        expires_in_seconds=900,
        mode=order.mode,
        provider=order.provider_driver,
        is_test=order.is_test,
    )


@router.get(
    "/check/{merchant_txn_id}",
    response_model=PaymentVerifyResponse,
    status_code=status.HTTP_200_OK,
)
async def check_payment_status(
    merchant_txn_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Public status lookup — the order ref is a random, unguessable id."""
    order = await PaymentService.get_order(db, merchant_txn_id)
    if not order:
        raise HTTPException(404, "Payment transaction not found.")
    return PaymentVerifyResponse(
        merchant_txn_id=order.order_ref,
        order_ref=order.order_ref,
        status=legacy_status(order.status),
        order_status=order.status,
        amount_inr=order.amount_paise,
        plan_name=order.plan_name,
        subscription_activated=order.status == "paid",
        mode=order.mode,
        provider=order.provider_driver,
        is_test=order.is_test,
    )


@router.get("/history", response_model=List[PaymentHistoryResponse])
async def get_payment_history(
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    orders = (
        await db.execute(
            select(PaymentOrder)
            .where(PaymentOrder.user_id == current_user.id)
            .order_by(PaymentOrder.created_at.desc())
        )
    ).scalars().all()
    return [PaymentService.serialize(order) for order in orders]


@router.get("/all", response_model=List[AdminPaymentHistoryResponse])
async def get_all_payments(
    current_admin: CurrentAdmin = Depends(require_superadmin),
    db: AsyncSession = Depends(get_db),
):
    rows = (
        await db.execute(
            select(PaymentOrder, User)
            .outerjoin(User, PaymentOrder.user_id == User.id)
            .order_by(PaymentOrder.created_at.desc())
        )
    ).all()
    return [PaymentService.serialize(order, user) for order, user in rows]



@router.get("/demo/{order_ref}", response_class=HTMLResponse)
async def demo_checkout(
    order_ref: str,
    db: AsyncSession = Depends(get_db),
):
    order = await PaymentService.get_order(db, order_ref)
    if not order or order.mode != "demo":
        raise HTTPException(404, "Demo order not found.")
    if order.status == "paid":
        return RedirectResponse(f"/payment/status?txn_id={order_ref}")
    return HTMLResponse(
        demo_checkout_page(
            order_ref,
            order.plan_name or "Plan",
            order.amount_paise,
            "Demo order — it is marked paid locally and never calls a provider.",
        )
    )


@router.post("/demo/{order_ref}/complete")
async def complete_demo_payment(
    order_ref: str,
    payload: DemoCompleteRequest,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    redis: aioredis.Redis = Depends(get_redis_client),
    _billing_enabled: None = Depends(require_billing_enabled),
):
    order = await PaymentService.get_order(db, order_ref)
    if not order or order.mode != "demo":
        raise HTTPException(404, "Demo order not found.")
    if order.user_id != current_user.id:
        raise HTTPException(403, "This order belongs to another user.")
    if not settings.payments_demo_allowed:
        raise HTTPException(409, "This payment can no longer be completed.")
    if await PaymentService.get_environment(db) != "demo":
        raise HTTPException(409, "This payment can no longer be completed.")

    provider = (
        await db.execute(
            select(PaymentProvider).where(PaymentProvider.id == order.provider_id)
        )
    ).scalar_one_or_none()
    if not provider or not provider.is_active or provider.driver != "demo":
        raise HTTPException(409, "This payment can no longer be completed.")
    if order.expires_at and order.expires_at < datetime.now(timezone.utc):
        await PaymentService.mark_failed(
            db=db, order=order, reason="Demo order expired."
        )
        await db.commit()
        raise HTTPException(409, "This payment can no longer be completed.")

    if payload.result == "success":
        try:
            await PaymentService.mark_paid(
                db=db,
                redis=redis,
                order=order,
                amount_paise=order.amount_paise,
                provider_payment_id=f"demo_{order_ref}",
                payment_method="DEMO",
            )
        except PaymentAmountError as exc:
            await db.commit()
            raise HTTPException(400, str(exc))
        await db.commit()
    else:
        await PaymentService.mark_failed(
            db=db, order=order, reason="Simulated failure"
        )
        await db.commit()
    return {"status": "ok", "order_status": legacy_status(order.status)}



@router.get("/checkout/{driver}/{order_ref}", response_class=HTMLResponse)
async def driver_checkout_page(
    driver: str,
    order_ref: str,
    db: AsyncSession = Depends(get_db),
):
    order = await PaymentService.get_order(db, order_ref)
    if not order or order.provider_driver != driver:
        raise HTTPException(404, "Payment order not found.")
    if order.status == "paid":
        return RedirectResponse(f"/payment/status?txn_id={order_ref}")
    provider = (
        await db.execute(
            select(PaymentProvider).where(PaymentProvider.id == order.provider_id)
        )
    ).scalar_one_or_none()
    if not provider:
        raise HTTPException(404, "Payment provider no longer exists.")

    try:
        credentials = PaymentService.decrypt_credentials(provider)
        page = get_driver(driver).checkout_page(
            order=order, credentials=credentials, mode=order.mode
        )
    except (PaymentServiceError, PaymentDriverError) as exc:
        logger.error(
            "payment.checkout.page_failed driver=%s mode=%s ref=%s: %s",
            driver,
            order.mode,
            order_ref,
            exc,
        )
        raise HTTPException(400, "This payment could not be opened. Return to Plans and try again.")
    if not page:
        if order.payment_url:
            return RedirectResponse(order.payment_url)
        raise HTTPException(400, "This payment could not be opened. Return to Plans and try again.")
    return HTMLResponse(page)



@router.api_route("/return/{provider_id}/{mode}", methods=["GET", "POST"])
async def payment_return(
    provider_id: str,
    mode: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    order_ref: Optional[str] = request.query_params.get("txn_id")
    order_ref = order_ref or request.query_params.get("order")
    if not order_ref and request.method == "POST":
        try:
            form = await request.form()
            order_ref = (
                form.get("txnid")
                or form.get("orderId")
                or form.get("order_id")
                or form.get("ORDERID")
            )
        except Exception:
            order_ref = None
    if order_ref:
        return RedirectResponse(f"/payment/status?txn_id={order_ref}")
    return RedirectResponse("/payment/status")



@router.post("/webhook/{provider_id}/{mode}", status_code=status.HTTP_200_OK)
async def payment_webhook(
    provider_id: str,
    mode: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    redis: aioredis.Redis = Depends(get_redis_client),
):
    try:
        provider_uuid = uuid.UUID(provider_id)
    except ValueError:
        raise HTTPException(404, "Unknown provider.")

    provider = (
        await db.execute(
            select(PaymentProvider).where(PaymentProvider.id == provider_uuid)
        )
    ).scalar_one_or_none()
    if not provider or provider.mode != mode:
        raise HTTPException(404, "Unknown provider or mode.")

    raw_body = await request.body()
    headers = {k.lower(): v for k, v in request.headers.items()}
    try:
        credentials = PaymentService.decrypt_credentials(provider)
        result = get_driver(provider.driver).verify_webhook(
            credentials=credentials,
            headers=headers,
            raw_body=raw_body,
            config=provider.config,
        )
    except SignatureError as exc:
        logger.warning("payment.webhook.bad_signature provider=%s: %s", provider.id, exc)
        raise HTTPException(401, "Invalid webhook signature.")
    except PaymentServiceError as exc:
        logger.error("payment.webhook.credentials provider=%s: %s", provider.id, exc)
        raise HTTPException(503, "Payment provider credentials unavailable.")
    except PaymentDriverError as exc:
        logger.warning("payment.webhook.invalid provider=%s: %s", provider.id, exc)
        raise HTTPException(400, str(exc))

    payload_hash = hashlib.sha256(raw_body).hexdigest()
    event = PaymentEvent(
        provider_id=provider.id,
        driver=provider.driver,
        mode=provider.mode,
        event_id=result.event_id or payload_hash,
        event_type=result.event_type,
        signature_valid=True,
        payload_hash=payload_hash,
        status="received",
    )
    db.add(event)
    try:
        await db.flush()
    except IntegrityError:
        await db.rollback()
        return {"status": "ok", "detail": "duplicate"}

    order = None
    if result.order_ref:
        order = await PaymentService.get_order(db, result.order_ref)
    if not order and result.provider_order_id:
        order = (
            await db.execute(
                select(PaymentOrder).where(
                    PaymentOrder.provider_order_id == result.provider_order_id
                )
            )
        ).scalar_one_or_none()

    if not order or order.provider_id != provider.id or order.mode != provider.mode:
        event.status = "ignored"
        event.error = "Order not found for this provider/mode."
        await db.commit()
        return {"status": "ok", "detail": "ignored"}

    event.order_id = order.id

    active_mode = await PaymentService.get_environment(db)
    if provider.mode != active_mode:
        event.status = "ignored"
        event.error = "Provider mode is not the active checkout environment."
        await db.commit()
        logger.warning(
            "payment.webhook.stale_mode provider=%s mode=%s active=%s ref=%s",
            provider.id,
            provider.mode,
            active_mode,
            order.order_ref,
        )
        return {"status": "ok", "detail": "ignored"}

    if (
        result.status == "paid"
        and result.amount_paise is not None
        and int(result.amount_paise) != int(order.amount_paise)
    ):
        order.status = "failed"
        order.failure_reason = (
            f"Amount mismatch: expected {order.amount_paise} paise, "
            f"got {result.amount_paise}."
        )
        event.status = "failed"
        event.error = order.failure_reason
        await db.commit()
        return {"status": "ok", "detail": "amount_mismatch"}

    platform_mode = await PlatformConfigService.get_mode_fresh(db)
    if platform_mode != PAID:
        # Acknowledge the money but never grant paid access on a free platform.
        if result.status == "paid":
            order.status = "paid"
            order.paid_at = datetime.now(timezone.utc)
            order.failure_reason = (
                "Paid while the platform is in free mode; no plan granted."
            )
        event.status = "ignored"
        event.error = "Platform is in free mode."
        await db.commit()
        return {"status": "ok", "detail": "free_mode"}

    try:
        if result.status == "paid":
            granted = await PaymentService.mark_paid(
                db=db,
                redis=redis,
                order=order,
                amount_paise=result.amount_paise,
                provider_payment_id=result.provider_payment_id,
                payment_method=result.payment_method,
            )
            event.status = "processed"
            if not granted:
                event.error = "Payment recorded; plan not changed (higher plan active)."
        elif result.status == "failed":
            await PaymentService.mark_failed(
                db=db,
                order=order,
                reason=result.event_type or "Provider reported failure",
            )
            event.status = "processed"
        else:
            event.status = "ignored"
        await db.commit()
    except PaymentAmountError as exc:
        event.status = "failed"
        event.error = str(exc)
        await db.commit()
        logger.error("payment.webhook.amount_mismatch ref=%s: %s", order.order_ref, exc)
    except Exception as exc:  # pragma: no cover - defensive
        await db.rollback()
        logger.exception("payment.webhook.failed provider=%s", provider.id)
        raise HTTPException(500, "Webhook processing failed.") from exc

    return {"status": "ok"}
