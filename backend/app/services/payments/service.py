"""Payment orchestration: environment, orders, credential handling, crediting."""

import asyncio
import json
import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

import httpx
import redis.asyncio as aioredis
from fastapi import HTTPException
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.config import get_settings
from app.models.payment import PaymentOrder, PaymentProvider
from app.models.plan import Plan
from app.models.platform_setting import PlatformSetting
from app.models.subscription import UserSubscription
from app.models.user import User
from app.services.payments.base import PaymentDriverError
from app.services.payments.registry import get_driver
from app.services.subscription import SubscriptionService
from app.utils.crypto import decrypt_payment_secret, encrypt_payment_secret

settings = get_settings()
logger = logging.getLogger("vidhya.payments")

MODES = ("demo", "sandbox", "production")
ORDER_TTL_MINUTES = 15


PAYMENT_START_FAILED = (
    "We couldn't start this payment right now. Please try again in a moment."
)


class PaymentServiceError(Exception):
    pass


class PaymentAmountError(PaymentServiceError):
    pass


def _now() -> datetime:
    return datetime.now(timezone.utc)


def legacy_status(value: str) -> str:
    if value == "paid":
        return "success"
    if value in ("failed", "expired", "refunded"):
        return "failed"
    return "pending"


class PaymentService:
    @staticmethod
    async def get_settings_row(db: AsyncSession) -> PlatformSetting:
        row = (
            await db.execute(select(PlatformSetting).where(PlatformSetting.id == 1))
        ).scalar_one_or_none()
        if not row:
            row = PlatformSetting(id=1)
            db.add(row)
            await db.flush()
        return row

    @classmethod
    async def get_environment(cls, db: AsyncSession) -> str:
        row = await cls.get_settings_row(db)
        mode = (row.payments_environment or "demo").lower()
        return mode if mode in MODES else "demo"

    @classmethod
    async def set_environment(cls, db: AsyncSession, mode: str) -> str:
        if mode not in MODES:
            raise HTTPException(400, "Payments environment must be demo, sandbox or production.")
        if mode == "demo" and not settings.payments_demo_allowed:
            raise HTTPException(
                400, "Demo payments are disabled in production. Use sandbox or production."
            )
        row = await cls.get_settings_row(db)
        previous = (row.payments_environment or "demo").lower()
        if previous != mode:
            # A pending order from the previous environment must never be
            # creditable after the switch.
            await db.execute(
                update(PaymentOrder)
                .where(
                    PaymentOrder.mode == previous,
                    PaymentOrder.status.in_(("created", "pending")),
                )
                .values(
                    status="expired",
                    failure_reason="Expired when the checkout environment changed.",
                )
            )
        row.payments_environment = mode
        return mode

    @staticmethod
    async def get_active_provider(
        db: AsyncSession, mode: str
    ) -> Optional[PaymentProvider]:
        return (
            await db.execute(
                select(PaymentProvider).where(
                    PaymentProvider.mode == mode,
                    PaymentProvider.is_active.is_(True),
                )
            )
        ).scalar_one_or_none()

    @staticmethod
    def decrypt_credentials(provider: PaymentProvider) -> Dict[str, str]:
        if not provider.credentials_encrypted:
            return {}
        try:
            raw = decrypt_payment_secret(provider.credentials_encrypted)
        except RuntimeError as exc:
            raise PaymentServiceError(str(exc)) from exc
        except Exception as exc:
            raise PaymentServiceError(
                "Could not decrypt this provider's credentials. "
                "Check PAYMENTS_ENCRYPTION_KEY or re-save the credentials."
            ) from exc
        try:
            data = json.loads(raw)
        except Exception as exc:
            raise PaymentServiceError("Stored payment credentials are corrupted.") from exc
        return {str(k): str(v) for k, v in data.items() if v is not None}


    @staticmethod
    def encrypt_credentials(credentials: Dict[str, Any]) -> str:
        clean = {
            str(k): str(v).strip()
            for k, v in credentials.items()
            if v is not None and str(v).strip() != ""
        }
        return encrypt_payment_secret(json.dumps(clean))

    @staticmethod
    def public_base() -> str:
        return settings.APP_URL.rstrip("/")

    @classmethod
    def return_url(cls, order_ref: str) -> str:
        return f"{cls.public_base()}/payment/status?txn_id={order_ref}"

    @classmethod
    def webhook_url(cls, provider: PaymentProvider) -> str:
        return (
            f"{cls.public_base()}/api/v1/payments/webhook/"
            f"{provider.id}/{provider.mode}"
        )

    @classmethod
    async def create_order(
        cls,
        *,
        user: User,
        plan_id: uuid.UUID,
        idempotency_key: Optional[str],
        db: AsyncSession,
    ) -> PaymentOrder:
        plan = (
            await db.execute(select(Plan).where(Plan.id == plan_id))
        ).scalar_one_or_none()
        if not plan or not plan.is_active:
            raise HTTPException(404, "Plan not found or deactivated.")
        if plan.is_free:
            raise HTTPException(400, "The free plan cannot be purchased.")

        active_sub = (
            await db.execute(
                select(UserSubscription)
                .options(joinedload(UserSubscription.plan))
                .where(
                    UserSubscription.user_id == user.id,
                    UserSubscription.status == "active",
                )
            )
        ).scalar_one_or_none()
        if active_sub and not active_sub.plan.is_free:
            if active_sub.plan_id == plan.id:
                raise HTTPException(409, f"You already have {plan.display_name} active.")
            if active_sub.plan.price_inr > plan.price_inr:
                raise HTTPException(
                    409,
                    f"You currently have a higher tier plan "
                    f"({active_sub.plan.display_name}). Downgrading is not permitted here.",
                )

        if idempotency_key:
            existing = (
                await db.execute(
                    select(PaymentOrder).where(
                        PaymentOrder.user_id == user.id,
                        PaymentOrder.idempotency_key == idempotency_key,
                        PaymentOrder.status.in_(("created", "pending")),
                    )
                )
            ).scalar_one_or_none()
            if existing:
                return existing

        mode = await cls.get_environment(db)
        if mode == "demo" and not settings.payments_demo_allowed:
            raise HTTPException(409, "Demo payments are disabled in production.")
        provider = await cls.get_active_provider(db, mode)
        if not provider:
            logger.error("payment.start.no_active_provider mode=%s", mode)
            raise HTTPException(503, PAYMENT_START_FAILED)

        try:
            credentials = cls.decrypt_credentials(provider)
        except PaymentServiceError:
            logger.exception(
                "payment.start.credentials provider=%s mode=%s",
                provider.id,
                mode,
            )
            raise HTTPException(503, PAYMENT_START_FAILED)
        driver = get_driver(provider.driver)
        if provider.driver != "demo" and provider.last_test_status != "ok":
            logger.error(
                "payment.start.provider_untested provider=%s mode=%s", provider.id, mode
            )
            raise HTTPException(503, PAYMENT_START_FAILED)
        missing = driver.validate_credentials(credentials)
        if missing:
            logger.error(
                "payment.start.missing_credentials provider=%s fields=%s",
                provider.id,
                missing,
            )
            raise HTTPException(503, PAYMENT_START_FAILED)

        order_ref = f"ORD{uuid.uuid4().hex[:20].upper()}"
        order = PaymentOrder(
            user_id=user.id,
            plan_id=plan.id,
            provider_id=provider.id,
            provider_driver=provider.driver,
            mode=mode,
            is_test=mode != "production",
            order_ref=order_ref,
            idempotency_key=idempotency_key,
            plan_name=plan.display_name,
            plan_snapshot=plan.to_snapshot(),
            amount_paise=plan.price_inr * 100,
            currency="INR",
            status="created",
            expires_at=_now() + timedelta(minutes=ORDER_TTL_MINUTES),
        )
        db.add(order)
        await db.flush()

        try:
            result = await driver.create_checkout(
                order=order,
                credentials=credentials,
                user=user,
                return_url=cls.return_url(order_ref),
                webhook_url=cls.webhook_url(provider),
                public_base=cls.public_base(),
            )
        except PaymentDriverError as exc:
            logger.error(
                "payment.start.driver_error provider=%s driver=%s mode=%s ref=%s: %s",
                provider.id,
                provider.driver,
                mode,
                order_ref,
                exc,
            )
            order.status = "failed"
            order.failure_reason = str(exc)[:500]
            await db.commit()
            raise HTTPException(502, PAYMENT_START_FAILED)
        except Exception:
            logger.exception(
                "payment.start.unexpected provider=%s driver=%s mode=%s ref=%s",
                provider.id,
                provider.driver,
                mode,
                order_ref,
            )
            order.status = "failed"
            order.failure_reason = "Payment provider request failed."
            await db.commit()
            raise HTTPException(502, PAYMENT_START_FAILED)

        order.provider_order_id = result.provider_order_id
        order.payment_url = result.payment_url
        order.provider_payload = result.payload or {}
        order.status = "pending"
        await db.commit()
        await db.refresh(order)
        return order

    @classmethod
    async def get_order(
        cls, db: AsyncSession, order_ref: str, for_update: bool = False
    ) -> Optional[PaymentOrder]:
        stmt = select(PaymentOrder).where(PaymentOrder.order_ref == order_ref)
        if for_update:
            stmt = stmt.with_for_update()
        return (await db.execute(stmt)).scalar_one_or_none()

    @classmethod
    async def mark_paid(
        cls,
        *,
        db: AsyncSession,
        redis: aioredis.Redis,
        order: PaymentOrder,
        amount_paise: Optional[int],
        provider_payment_id: Optional[str] = None,
        payment_method: Optional[str] = None,
    ) -> bool:
        """Credit an order exactly once. Caller commits."""
        locked = await cls.get_order(db, order.order_ref, for_update=True)
        if not locked or locked.status == "paid":
            return False
        if locked.status not in ("created", "pending"):
            return False
        if amount_paise is not None and int(amount_paise) != int(locked.amount_paise):
            locked.status = "failed"
            locked.failure_reason = (
                f"Amount mismatch: expected {locked.amount_paise} paise, "
                f"got {amount_paise}."
            )
            raise PaymentAmountError(locked.failure_reason)

        locked.status = "paid"
        locked.paid_at = _now()
        locked.provider_payment_id = provider_payment_id or locked.provider_payment_id
        locked.payment_method = payment_method or locked.payment_method

        plan = None
        if locked.plan_id:
            plan = (
                await db.execute(select(Plan).where(Plan.id == locked.plan_id))
            ).scalar_one_or_none()

        granted = False
        if plan:
            subscription = await SubscriptionService.activate_paid_plan(
                user_id=locked.user_id,
                plan=plan,
                payment_id=locked.id,
                db=db,
                redis=redis,
            )
            granted = subscription is not None
            if subscription:
                user = (
                    await db.execute(select(User).where(User.id == locked.user_id))
                ).scalar_one_or_none()
                if user:
                    asyncio.create_task(
                        cls._notify_telegram(user, plan, locked, provider_payment_id)
                    )
        else:
            locked.failure_reason = (
                "Payment captured, but the plan no longer exists. Grant manually or refund."
            )
        return granted

    @staticmethod
    async def mark_failed(
        *,
        db: AsyncSession,
        order: PaymentOrder,
        reason: str,
    ) -> None:
        locked = await PaymentService.get_order(db, order.order_ref, for_update=True)
        if not locked or locked.status == "paid":
            return
        locked.status = "failed"
        locked.failure_reason = reason[:500]


    @staticmethod
    async def _notify_telegram(
        user: User, plan: Plan, order: PaymentOrder, provider_payment_id: Optional[str]
    ) -> None:
        if not user.telegram_id or not settings.TELEGRAM_BOT_TOKEN:
            return
        text = (
            "🎉 *Payment Successful!* 🌟\n\n"
            f"Thank you for upgrading to *{plan.display_name}*.\n"
            f"Amount Paid: *₹{order.amount_paise / 100:.2f}*\n"
            f"Transaction Ref: `{provider_payment_id or order.order_ref}`\n\n"
            "Your new plan is now active! Enjoy your premium features. 🚀"
        )
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                await client.post(
                    f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/sendMessage",
                    json={
                        "chat_id": user.telegram_id,
                        "text": text,
                        "parse_mode": "Markdown",
                    },
                )
        except Exception as exc:  # pragma: no cover - best effort
            logger.warning("Telegram payment notification failed: %s", exc)

    @staticmethod
    def serialize(order: PaymentOrder, user: Optional[User] = None) -> Dict[str, Any]:
        return {
            "id": str(order.id),
            "merchant_txn_id": order.order_ref,
            "order_ref": order.order_ref,
            "provider_transaction_id": order.provider_payment_id,
            "amount_inr": order.amount_paise,
            "amount_paise": order.amount_paise,
            "currency": order.currency,
            "status": legacy_status(order.status),
            "order_status": order.status,
            "payment_method": order.payment_method,
            "plan_name": order.plan_name,
            "provider": order.provider_driver,
            "mode": order.mode,
            "is_test": order.is_test,
            "initiated_at": order.created_at,
            "completed_at": order.paid_at,
            "created_at": order.created_at,
            "user_email": (
                (user.email or user.username or (f"tg:{user.telegram_id}" if user.telegram_id else str(user.id)))
                if user
                else None
            ),
            "user_name": user.first_name if user else None,
        }
