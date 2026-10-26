"""PhonePe driver — redirect checkout + signed S2S callbacks."""

import base64
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

SANDBOX_BASE = "https://api-preprod.phonepe.com/apis/pg-sandbox"
PROD_BASE = "https://api.phonepe.com/apis/hermes"


class PhonePeDriver(PaymentDriver):
    meta = ProviderMeta(
        driver="phonepe",
        name="PhonePe",
        tagline="UPI-first checkout with cards, netbanking and wallets.",
        brand_slug="phonepe",
        brand_color="#5F259F",
        docs_url="https://developer.phonepe.com/payment-gateway/uat-testing-go-live/uat-sandbox",
        fields=(
            CredentialField(
                key="merchant_id",
                label="Merchant ID",
                hint="PhonePe Business dashboard → Developer Settings.",
                secret=False,
            ),
            CredentialField(key="salt_key", label="Salt Key", hint="Shown with the Merchant ID."),
            CredentialField(
                key="salt_index",
                label="Salt Index",
                hint="Usually 1. Used in the X-VERIFY checksum.",
                secret=False,
                default="1",
            ),
            CredentialField(
                key="webhook_username",
                label="Webhook username",
                hint="Created under the Webhooks tab; used for Basic auth on callbacks.",
                secret=False,
                required=False,
            ),
            CredentialField(
                key="webhook_password",
                label="Webhook password",
                hint="The password shown when the webhook was created.",
                required=False,
            ),
        ),
        capabilities=("UPI intent", "UPI QR", "Cards", "Netbanking", "Wallets"),
        webhook_events=("Payment success callback", "Payment failure callback"),
        webhook_notes="Create a webhook in PhonePe with our URL and username/password. PhonePe posts an S2S callback.",
    )

    def _base(self, mode: str) -> str:
        return SANDBOX_BASE if mode != "production" else PROD_BASE

    def _checksum(self, payload: str, salt_key: str, salt_index: str) -> str:
        digest = hashlib.sha256(f"{payload}{salt_key}".encode()).hexdigest()
        return f"{digest}###{salt_index}"

    def _request_checksum(self, path: str, salt_key: str, salt_index: str) -> str:
        digest = hashlib.sha256(f"{path}{salt_key}".encode()).hexdigest()
        return f"{digest}###{salt_index}"

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
        payload = {
            "merchantId": credentials["merchant_id"],
            "merchantTransactionId": order.order_ref,
            "merchantUserId": f"USER-{str(user.id)[:24]}",
            "amount": order.amount_paise,
            "redirectUrl": return_url,
            "redirectMode": "REDIRECT",
            "callbackUrl": webhook_url,
            "paymentInstrument": {"type": "PAY_PAGE"},
        }
        encoded = base64.b64encode(json.dumps(payload).encode()).decode()
        verify = self._request_checksum(
            encoded + "/pg/v1/pay", credentials["salt_key"], credentials["salt_index"]
        )
        async with httpx.AsyncClient(timeout=20.0) as client:
            res = await client.post(
                f"{self._base(order.mode)}/pg/v1/pay",
                json={"request": encoded},
                headers={
                    "Content-Type": "application/json",
                    "X-VERIFY": verify,
                    "accept": "application/json",
                },
            )
        data = res.json() if res.content else {}
        if res.status_code >= 400 or not data.get("success"):
            raise PaymentDriverError(
                f"PhonePe rejected the order: {data.get('message') or res.text[:200]}"
            )
        redirect = (
            (data.get("data") or {}).get("instrumentResponse", {}).get("redirectInfo", {})
        ).get("url")
        if not redirect:
            raise PaymentDriverError("PhonePe did not return a redirect URL.")
        return CheckoutResult(
            provider_order_id=order.order_ref,
            payment_url=redirect,
            payload={"redirect_url": redirect},
        )

    def verify_webhook(
        self,
        *,
        credentials: Dict[str, str],
        headers: Dict[str, str],
        raw_body: bytes,
        config: Optional[Dict[str, Any]] = None,
    ) -> WebhookResult:
        try:
            body = json.loads(raw_body.decode("utf-8"))
            encoded = body.get("response") if isinstance(body, dict) else None
        except Exception:
            encoded = None
        if not encoded:
            encoded = raw_body.decode("utf-8").strip()

        # Basic auth is transport-level only. The X-VERIFY checksum is the
        # cryptographic proof and must be present for every callback.
        x_verify = headers.get("x-verify", "")
        expected_verify = self._checksum(
            encoded, credentials["salt_key"], credentials["salt_index"]
        )
        if not x_verify or not hmac.compare_digest(x_verify, expected_verify):
            raise SignatureError("Invalid PhonePe callback signature.")

        try:
            data = json.loads(base64.b64decode(encoded).decode("utf-8"))
        except Exception as exc:
            raise PaymentDriverError(f"Could not decode the PhonePe callback: {exc}")

        payload = data.get("data") or {}
        order_ref = payload.get("merchantTransactionId", "")
        code = data.get("code", "")
        state = "paid" if code == "PAYMENT_SUCCESS" else (
            "failed" if code in ("PAYMENT_ERROR", "PAYMENT_DECLINED") else "ignored"
        )
        instrument = payload.get("paymentInstrument") or {}
        return WebhookResult(
            order_ref=order_ref,
            status=state,
            amount_paise=payload.get("amount"),
            event_id=f"{order_ref}:{payload.get('transactionId', '')}:{code}",
            event_type=code or "payment",
            provider_order_id=order_ref,
            provider_payment_id=payload.get("transactionId"),
            payment_method=(instrument.get("type") or "").upper() or None,
            raw=data,
        )

    async def fetch_status(
        self,
        *,
        order,
        credentials: Dict[str, str],
    ) -> StatusResult:
        path = (
            f"/pg/v1/status/{credentials['merchant_id']}/{order.order_ref}"
        )
        verify = self._request_checksum(
            path, credentials["salt_key"], credentials["salt_index"]
        )
        async with httpx.AsyncClient(timeout=20.0) as client:
            res = await client.get(
                f"{self._base(order.mode)}{path}",
                headers={"X-VERIFY": verify, "accept": "application/json"},
            )
        data = res.json() if res.content else {}
        if res.status_code >= 400:
            raise PaymentDriverError(f"PhonePe status failed ({res.status_code}).")
        payload = data.get("data") or {}
        code = data.get("code", "")
        state = "paid" if code == "PAYMENT_SUCCESS" else (
            "failed" if code in ("PAYMENT_ERROR", "PAYMENT_DECLINED") else "pending"
        )
        return StatusResult(
            status=state,
            amount_paise=payload.get("amount"),
            provider_payment_id=payload.get("transactionId"),
            raw=data,
        )

    async def test_credentials(
        self,
        *,
        credentials: Dict[str, str],
        mode: str,
    ) -> str:
        path = f"/pg/v1/status/{credentials['merchant_id']}/TEST{hashlib.md5(credentials['merchant_id'].encode()).hexdigest()[:10]}"
        verify = self._request_checksum(
            path, credentials["salt_key"], credentials["salt_index"]
        )
        async with httpx.AsyncClient(timeout=20.0) as client:
            res = await client.get(
                f"{self._base(mode)}{path}",
                headers={"X-VERIFY": verify, "accept": "application/json"},
            )
        if res.status_code in (401, 403):
            raise PaymentDriverError("PhonePe rejected the Merchant ID or Salt Key.")
        if res.status_code >= 500:
            raise PaymentDriverError(f"PhonePe test failed ({res.status_code}).")
        return "PhonePe credentials accepted."
