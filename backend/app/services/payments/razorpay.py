"""Razorpay driver — hosted Payment Links + signed webhooks."""

import hashlib
import hmac
import json
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

BASE = "https://api.razorpay.com/v1"


class RazorpayDriver(PaymentDriver):
    meta = ProviderMeta(
        driver="razorpay",
        name="Razorpay",
        tagline="UPI, cards, netbanking, wallets, EMI and subscriptions.",
        brand_slug="razorpay",
        brand_color="#0C2451",
        docs_url="https://razorpay.com/docs/payments/dashboard/account-settings/api-keys",
        fields=(
            CredentialField(
                key="key_id",
                label="Key ID",
                hint="Dashboard → Settings → API Keys (Test or Live).",
                secret=False,
                placeholder="rzp_test_… or rzp_live_…",
            ),
            CredentialField(
                key="key_secret",
                label="Key Secret",
                hint="Shown once next to the Key ID.",
            ),
            CredentialField(
                key="webhook_secret",
                label="Webhook Secret",
                hint="The secret you set while creating the webhook in Razorpay.",
            ),
        ),
        capabilities=("UPI intent", "UPI QR", "Cards", "Netbanking", "Wallets", "EMI", "Subscriptions"),
        webhook_events=("payment_link.paid", "payment_link.cancelled", "payment_link.expired"),
        webhook_notes="Create the webhook in Settings → Webhooks, paste our URL, set the same secret and select the events above.",
    )

    def _auth(self, c: Dict[str, str]) -> httpx.BasicAuth:
        return httpx.BasicAuth(c["key_id"], c["key_secret"])

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
        body: Dict[str, Any] = {
            "amount": order.amount_paise,
            "currency": "INR",
            "accept_partial": False,
            "reference_id": order.order_ref,
            "description": f"{order.plan_name or 'Vidhya'} plan",
            "callback_url": return_url,
            "callback_method": "get",
            "reminder_enable": False,
            "notes": {"order_ref": order.order_ref},
        }
        customer: Dict[str, str] = {}
        if user.first_name:
            customer["name"] = user.first_name
        if user.email:
            customer["email"] = user.email
        if user.mobile:
            customer["contact"] = user.mobile
        if customer:
            body["customer"] = customer

        async with httpx.AsyncClient(timeout=20.0) as client:
            res = await client.post(
                f"{BASE}/payment_links", json=body, auth=self._auth(credentials)
            )
        if res.status_code >= 400:
            raise PaymentDriverError(
                f"Razorpay rejected the order ({res.status_code}): {res.text[:300]}"
            )
        data = res.json()
        if not data.get("short_url") or not data.get("id"):
            raise PaymentDriverError("Razorpay did not return a payment link.")
        return CheckoutResult(
            provider_order_id=data["id"],
            payment_url=data["short_url"],
            payload={"payment_link_id": data["id"]},
        )

    def verify_webhook(
        self,
        *,
        credentials: Dict[str, str],
        headers: Dict[str, str],
        raw_body: bytes,
        config: Optional[Dict[str, Any]] = None,
    ) -> WebhookResult:
        signature = headers.get("x-razorpay-signature", "")
        expected = hmac.new(
            credentials["webhook_secret"].encode(), raw_body, hashlib.sha256
        ).hexdigest()
        if not signature or not hmac.compare_digest(signature, expected):
            raise SignatureError("Invalid Razorpay webhook signature.")

        data = json.loads(raw_body.decode("utf-8"))
        event = data.get("event", "")
        payload = data.get("payload", {})
        link = payload.get("payment_link", {}).get("entity", {})
        payment = payload.get("payment", {}).get("entity", {})
        event_id = headers.get("x-razorpay-event-id") or hashlib.sha256(
            raw_body
        ).hexdigest()

        if not link:
            return WebhookResult(
                order_ref="",
                status="ignored",
                event_id=event_id,
                event_type=event,
                raw=data,
            )

        status = "ignored"
        if event == "payment_link.paid" or link.get("status") == "paid":
            status = "paid"
        elif event in ("payment_link.cancelled", "payment_link.expired"):
            status = "failed"

        return WebhookResult(
            order_ref=link.get("reference_id", ""),
            status=status,
            amount_paise=int(link.get("amount") or 0) or None,
            event_id=event_id,
            event_type=event,
            provider_order_id=link.get("id"),
            provider_payment_id=payment.get("id"),
            payment_method=(payment.get("method") or "").upper() or None,
            raw=data,
        )

    async def fetch_status(
        self,
        *,
        order,
        credentials: Dict[str, str],
    ) -> StatusResult:
        if not order.provider_order_id:
            return StatusResult(status="pending")
        async with httpx.AsyncClient(timeout=20.0) as client:
            res = await client.get(
                f"{BASE}/payment_links/{order.provider_order_id}",
                auth=self._auth(credentials),
            )
        if res.status_code >= 400:
            raise PaymentDriverError(f"Razorpay status failed ({res.status_code}).")
        data = res.json()
        state = data.get("status")
        status = "paid" if state == "paid" else (
            "failed" if state in ("cancelled", "expired") else "pending"
        )
        return StatusResult(status=status, amount_paise=data.get("amount"), raw=data)

    async def test_credentials(
        self,
        *,
        credentials: Dict[str, str],
        mode: str,
    ) -> str:
        async with httpx.AsyncClient(timeout=20.0) as client:
            res = await client.get(
                f"{BASE}/payment_links?count=1", auth=self._auth(credentials)
            )
        if res.status_code in (401, 403):
            raise PaymentDriverError("Razorpay rejected the Key ID or Key Secret.")
        if res.status_code >= 400:
            raise PaymentDriverError(
                f"Razorpay test failed ({res.status_code}): {res.text[:200]}"
            )
        return "Razorpay credentials accepted."
