"""PayU driver — hosted form post + hash-verified callbacks."""

import hashlib
import json
from typing import Any, Dict, Optional
from urllib.parse import parse_qs

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
from app.services.payments.pages import auto_post_page

SANDBOX_PAY = "https://test.payu.in/_payment"
PROD_PAY = "https://secure.payu.in/_payment"
SANDBOX_VERIFY = "https://test.payu.in/merchant/postservice.php?form=2"
PROD_VERIFY = "https://info.payu.in/merchant/postservice.php?form=2"


def _verify_url(mode: str) -> str:
    return SANDBOX_VERIFY if mode != "production" else PROD_VERIFY


def _sha512(value: str) -> str:
    return hashlib.sha512(value.encode()).hexdigest()


class PayUDriver(PaymentDriver):
    meta = ProviderMeta(
        driver="payu",
        name="PayU",
        tagline="UPI, cards, netbanking, wallets and EMI for Indian customers.",
        brand_slug="payu",
        brand_color="#A6C307",
        docs_url="https://docs.payu.in/docs/generate-test-merchant-key-and-salt",
        fields=(
            CredentialField(
                key="merchant_key",
                label="Merchant Key",
                hint="PayU Dashboard → switch to Test or Live → Payment Gateway → Developer → Key Salt Details.",
                secret=False,
            ),
            CredentialField(
                key="salt",
                label="Salt",
                hint="The Salt from the same environment as the Merchant Key. Sandbox and live pairs are different.",
            ),
        ),
        capabilities=("UPI intent", "UPI QR", "Cards", "Netbanking", "Wallets", "EMI", "BNPL"),
        webhook_events=("Payment success/failure callback", "Refund status"),
        webhook_notes="Add this URL as the webhook in the PayU dashboard. Success/Failure return URLs are generated per order.",
    )

    def _forward_hash(
        self, key: str, salt: str, txnid: str, amount: str,
        productinfo: str, firstname: str, email: str,
    ) -> str:
        parts = [key, txnid, amount, productinfo, firstname, email] + [""] * 10 + [salt]
        return _sha512("|".join(parts))

    def _reverse_hash(
        self, key: str, salt: str, txnid: str, amount: str,
        productinfo: str, firstname: str, email: str, status: str,
    ) -> str:
        parts = [salt, status] + [""] * 10 + [
            email, firstname, productinfo, amount, txnid, key,
        ]
        return _sha512("|".join(parts))

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
        key = credentials["merchant_key"]
        salt = credentials["salt"]
        amount = f"{order.amount_paise / 100:.2f}"
        productinfo = order.plan_name or "Vidhya plan"
        firstname = user.first_name or "Vidhya"
        email = user.email or f"user+{str(user.id)[:8]}@vidhya.local"
        fields = {
            "key": key,
            "txnid": order.order_ref,
            "amount": amount,
            "productinfo": productinfo,
            "firstname": firstname,
            "email": email,
            "phone": user.mobile or "9999999999",
            "surl": return_url,
            "furl": return_url,
            "service_provider": "payu_paisa",
            "hash": self._forward_hash(
                key, salt, order.order_ref, amount, productinfo, firstname, email
            ),
        }
        return CheckoutResult(
            provider_order_id=order.order_ref,
            payment_url=f"{public_base.rstrip('/')}/api/v1/payments/checkout/payu/{order.order_ref}",
            payload={"form": fields},
        )

    def verify_webhook(
        self,
        *,
        credentials: Dict[str, str],
        headers: Dict[str, str],
        raw_body: bytes,
        config: Optional[Dict[str, Any]] = None,
    ) -> WebhookResult:
        text = raw_body.decode("utf-8")
        if text.lstrip().startswith("{"):
            fields = json.loads(text)
        else:
            fields = {
                k: v[0]
                for k, v in parse_qs(text, keep_blank_values=True).items()
            }
        txnid = fields.get("txnid", "")
        status = (fields.get("status") or "").lower()
        amount = fields.get("amount", "")
        productinfo = fields.get("productinfo", "")
        firstname = fields.get("firstname", "")
        email = fields.get("email", "")
        received = (fields.get("hash") or "").lower()
        expected = self._reverse_hash(
            credentials["merchant_key"], credentials["salt"], txnid, amount,
            productinfo, firstname, email, status,
        )
        if not received or received != expected:
            raise SignatureError("Invalid PayU callback hash.")

        state = "paid" if status == "success" else (
            "failed" if status in ("failure", "failed") else "ignored"
        )
        return WebhookResult(
            order_ref=txnid,
            status=state,
            amount_paise=round(float(amount) * 100) if amount else None,
            event_id=f"{txnid}:{fields.get('mihpayid', '')}:{status}",
            event_type=status or "payment",
            provider_order_id=txnid,
            provider_payment_id=fields.get("mihpayid"),
            payment_method=(fields.get("mode") or "").upper() or None,
            raw=fields,
        )

    async def fetch_status(
        self,
        *,
        order,
        credentials: Dict[str, str],
    ) -> StatusResult:
        key = credentials["merchant_key"]
        salt = credentials["salt"]
        txnid = order.order_ref
        hash_value = _sha512(f"{key}|verify_payment|{txnid}|{salt}")
        data = {
            "key": key,
            "command": "verify_payment",
            "var1": txnid,
            "hash": hash_value,
        }
        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                res = await client.post(_verify_url(order.mode), data=data)
        except httpx.HTTPError as exc:
            raise PaymentDriverError(f"PayU status request failed: {exc}") from exc
        if res.status_code >= 400:
            raise PaymentDriverError(f"PayU status failed ({res.status_code}).")
        payload = res.json()
        details = (payload.get("transaction_details") or {}).get(txnid, {})
        state = (details.get("status") or "").lower()
        status = "paid" if state == "success" else (
            "failed" if state in ("failure", "failed") else "pending"
        )
        amount = details.get("amt") or details.get("amount")
        return StatusResult(
            status=status,
            amount_paise=round(float(amount) * 100) if amount else None,
            provider_payment_id=details.get("mihpayid"),
            raw=json.loads(json.dumps(payload)),
        )

    async def test_credentials(
        self,
        *,
        credentials: Dict[str, str],
        mode: str,
    ) -> str:
        key = credentials["merchant_key"]
        salt = credentials["salt"]
        txnid = "TEST" + hashlib.md5(key.encode()).hexdigest()[:10]
        data = {
            "key": key,
            "command": "verify_payment",
            "var1": txnid,
            "hash": _sha512(f"{key}|verify_payment|{txnid}|{salt}"),
        }
        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                res = await client.post(_verify_url(mode), data=data)
        except httpx.HTTPError as exc:
            raise PaymentDriverError(
                f"PayU connection failed: {exc}",
                safe_message="Could not reach PayU. Check the server connection and try again.",
            ) from exc

        body = res.text[:500]
        if res.status_code == 429:
            raise PaymentDriverError(
                f"PayU rate limited the verification request: {body}",
                safe_message="PayU is limiting test requests. Wait a few minutes and try again.",
            )
        if res.status_code >= 400:
            raise PaymentDriverError(
                f"PayU verification failed ({res.status_code}): {body}",
                safe_message=(
                    "PayU could not verify the Merchant Key and Salt. "
                    "Use the matching pair for this environment."
                ),
            )

        try:
            payload = res.json()
        except ValueError as exc:
            raise PaymentDriverError(
                f"PayU returned an invalid verification response: {body}",
                safe_message="PayU returned an unexpected response. Try again shortly.",
            ) from exc

        message = str(payload.get("msg") or "")
        lowered = message.lower()
        if "invalid hash" in lowered or "invalid key" in lowered or "authentication" in lowered:
            raise PaymentDriverError(
                f"PayU rejected the credential pair: {message}",
                safe_message=(
                    "PayU rejected the Merchant Key and Salt pair. Copy both again "
                    "from the same Test or Live environment."
                ),
            )
        if "transaction_details" not in payload:
            raise PaymentDriverError(
                f"PayU verification was not accepted: {message or body}",
                safe_message=(
                    "PayU could not verify these credentials. Check that the Merchant "
                    "Key and Salt belong to the same environment."
                ),
            )
        return "PayU credentials accepted."

    def checkout_page(
        self,
        *,
        order,
        credentials: Dict[str, str],
        mode: str,
    ) -> Optional[str]:
        fields = (order.provider_payload or {}).get("form")
        if not fields:
            return None
        return auto_post_page(
            "PayU checkout",
            f"Paying ₹{order.amount_paise / 100:,.2f} for {order.plan_name or 'your plan'}.",
            SANDBOX_PAY if mode != "production" else PROD_PAY,
            fields,
        )
