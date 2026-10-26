"""Cashfree driver — hosted checkout + HMAC webhooks."""

import hashlib
import hmac
import json
import time
import uuid
from typing import Any, Dict, Optional

import httpx

from app.services.payments.base import (
    CheckoutResult,
    CredentialField,
    PaymentDriver,
    PaymentDriverError,
    ProviderMeta,
    SignatureError,
    StatusResult,
    WebhookResult,
)
from app.services.payments.pages import cashfree_checkout_page

SANDBOX_BASE = "https://sandbox.cashfree.com/pg"
PROD_BASE = "https://api.cashfree.com/pg"
API_VERSION = "2023-08-01"


class CashfreeDriver(PaymentDriver):
    meta = ProviderMeta(
        driver="cashfree",
        name="Cashfree",
        tagline="UPI, cards, netbanking, wallets and recurring payments.",
        brand_slug="cashfree",
        brand_color="#6A4CF6",
        docs_url="https://www.cashfree.com/docs/api-reference/authentication",
        fields=(
            CredentialField(
                key="app_id",
                label="Payment Gateway App ID",
                hint="Merchant Dashboard → Payment Gateway → Developers → API Keys. Sandbox IDs usually begin TEST; production keys are separate.",
                secret=False,
                placeholder="TEST…",
            ),
            CredentialField(
                key="secret_key",
                label="Payment Gateway Secret Key",
                hint="The secret from the same app as the App ID — not a Payouts or Secure ID key. It also verifies webhooks.",
            ),
        ),
        capabilities=("UPI intent", "UPI QR", "Cards", "Netbanking", "Wallets", "AutoPay / eNACH"),
        webhook_events=(
            "PAYMENT_SUCCESS_WEBHOOK",
            "PAYMENT_FAILED_WEBHOOK",
            "PAYMENT_USER_DROPPED_WEBHOOK",
            "REFUND_STATUS_WEBHOOK",
        ),
        webhook_notes="Add the URL under Webhooks in the Cashfree dashboard and select the payment/refund events.",
    )

    def _base(self, mode: str) -> str:
        return SANDBOX_BASE if mode != "production" else PROD_BASE

    def _headers(self, c: Dict[str, str]) -> Dict[str, str]:
        return {
            "x-client-id": c["app_id"],
            "x-client-secret": c["secret_key"],
            "x-api-version": API_VERSION,
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    async def create_checkout(
        self,
        *,
        order,
        credentials: Dict[str, str],
        user,
        return_url: str,
        webhook_url: str,
        public_base: str,
    ) -> CheckoutResult:
        body = {
            "order_id": order.order_ref,
            "order_amount": round(order.amount_paise / 100, 2),
            "order_currency": "INR",
            "customer_details": {
                "customer_id": str(user.id)[:40],
                "customer_email": user.email or f"user+{str(user.id)[:8]}@vidhya.local",
                "customer_phone": user.mobile or "9999999999",
                "customer_name": user.first_name or "Vidhya user",
            },
            "order_meta": {"return_url": return_url},
            "order_note": f"{order.plan_name or 'Vidhya'} plan",
        }
        async with httpx.AsyncClient(timeout=20.0) as client:
            res = await client.post(
                f"{self._base(order.mode)}/orders",
                json=body,
                headers=self._headers(credentials),
            )
        if res.status_code >= 400:
            raise PaymentDriverError(
                f"Cashfree rejected the order ({res.status_code}): {res.text[:300]}"
            )
        data = res.json()
        session_id = data.get("payment_session_id")
        if not session_id:
            raise PaymentDriverError("Cashfree did not return a payment session.")
        return CheckoutResult(
            provider_order_id=data.get("order_id") or order.order_ref,
            payment_url=f"{public_base.rstrip('/')}/api/v1/payments/checkout/cashfree/{order.order_ref}",
            payload={"payment_session_id": session_id},
        )

    def verify_webhook(
        self,
        *,
        credentials: Dict[str, str],
        headers: Dict[str, str],
        raw_body: bytes,
        config: Optional[Dict[str, Any]] = None,
    ) -> WebhookResult:
        timestamp = headers.get("x-webhook-timestamp", "")
        signature = headers.get("x-webhook-signature", "")
        try:
            timestamp_seconds = float(timestamp)
            if timestamp_seconds > 10_000_000_000:
                timestamp_seconds /= 1000
        except (TypeError, ValueError):
            raise SignatureError("Invalid Cashfree webhook timestamp.")
        if abs(time.time() - timestamp_seconds) > 300:
            raise SignatureError("Expired Cashfree webhook.")

        signed = timestamp.encode() + raw_body
        expected = hmac.new(
            credentials["secret_key"].encode(), signed, hashlib.sha256
        ).hexdigest()
        if not signature or not hmac.compare_digest(signature, expected):
            raise SignatureError("Invalid Cashfree webhook signature.")

        data = json.loads(raw_body.decode("utf-8"))
        event = data.get("type", "")
        payload = data.get("data", {})
        order = payload.get("order", {}) or {}
        payment = payload.get("payment", {}) or {}
        event_id = str(
            payment.get("cf_payment_id")
            or order.get("order_id")
            or hashlib.sha256(raw_body).hexdigest()
        )
        payment_status = str(payment.get("payment_status", "")).upper()

        status = "ignored"
        if payment_status == "SUCCESS" or event == "PAYMENT_SUCCESS_WEBHOOK":
            status = "paid"
        elif payment_status in ("FAILED", "USER_DROPPED") or event in (
            "PAYMENT_FAILED_WEBHOOK",
            "PAYMENT_USER_DROPPED_WEBHOOK",
        ):
            status = "failed"

        amount = payment.get("payment_amount")
        return WebhookResult(
            order_ref=order.get("order_id", ""),
            status=status,
            amount_paise=round(float(amount) * 100) if amount is not None else None,
            event_id=event_id,
            event_type=event,
            provider_order_id=order.get("order_id"),
            provider_payment_id=str(payment.get("cf_payment_id") or "") or None,
            payment_method=(payment.get("payment_group") or "").upper() or None,
            raw=data,
        )

    async def fetch_status(
        self,
        *,
        order,
        credentials: Dict[str, str],
    ) -> StatusResult:
        async with httpx.AsyncClient(timeout=20.0) as client:
            res = await client.get(
                f"{self._base(order.mode)}/orders/{order.order_ref}",
                headers=self._headers(credentials),
            )
        if res.status_code >= 400:
            raise PaymentDriverError(f"Cashfree status failed ({res.status_code}).")
        data = res.json()
        state = str(data.get("order_status", "")).upper()
        status = "paid" if state == "PAID" else (
            "failed" if state in ("EXPIRED", "TERMINATED") else "pending"
        )
        return StatusResult(
            status=status,
            amount_paise=round(float(data.get("order_amount") or 0) * 100) or None,
            raw=data,
        )

    async def test_credentials(
        self,
        *,
        credentials: Dict[str, str],
        mode: str,
    ) -> str:
        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                res = await client.get(
                    f"{self._base(mode)}/orders/{uuid.uuid4().hex[:12]}",
                    headers=self._headers(credentials),
                )
        except httpx.HTTPError as exc:
            raise PaymentDriverError(
                f"Cashfree connection failed: {exc}",
                safe_message="Could not reach Cashfree. Check the server connection and try again.",
            ) from exc

        if res.status_code in (401, 403):
            raise PaymentDriverError(
                f"Cashfree authentication failed ({res.status_code}): {res.text[:300]}",
                safe_message=(
                    "Cashfree rejected the App ID or Secret Key. Use Payment Gateway "
                    f"{mode} keys from the same app — not Payouts or Secure ID keys."
                ),
            )
        if res.status_code not in (200, 404):
            raise PaymentDriverError(
                f"Cashfree connection test returned {res.status_code}: {res.text[:300]}",
                safe_message=(
                    "Cashfree could not verify these credentials. Check that both keys "
                    "belong to the same Payment Gateway app and environment."
                ),
            )
        return "Cashfree credentials accepted."

    def checkout_page(
        self,
        *,
        order,
        credentials: Dict[str, str],
        mode: str,
    ) -> Optional[str]:
        session_id = (order.provider_payload or {}).get("payment_session_id")
        if not session_id:
            return None
        return cashfree_checkout_page(
            "Cashfree checkout",
            f"Paying ₹{order.amount_paise / 100:,.2f} for {order.plan_name or 'your plan'}.",
            session_id,
            mode,
        )
