"""Paytm driver — hosted checkout + checksum-verified callbacks."""

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

try:  # Official Paytm checksum helper (listed in requirements.txt)
    from paytmchecksum import PaytmChecksum
except ImportError:  # pragma: no cover - surfaced as a clear error when used
    PaytmChecksum = None


SANDBOX_BASE = "https://securegw-stage.paytm.in"
PROD_BASE = "https://securegw.paytm.in"


def _checksum_module():
    if PaytmChecksum is None:
        raise PaymentDriverError(
            "The paytmchecksum package is not installed. Rebuild the backend image."
        )
    return PaytmChecksum


class PaytmDriver(PaymentDriver):
    meta = ProviderMeta(
        driver="paytm",
        name="Paytm",
        tagline="UPI, Paytm wallet/postpaid, cards, netbanking and EMI.",
        brand_slug="paytm",
        brand_color="#002970",
        docs_url="https://www.paytmpayments.com/docs/jscheckout-test-go-live",
        fields=(
            CredentialField(
                key="mid",
                label="Merchant ID (MID)",
                hint="Paytm for Business dashboard → Developer settings → API Keys.",
                secret=False,
                placeholder="Your MID",
            ),
            CredentialField(
                key="merchant_key",
                label="Merchant Key",
                hint="Shown next to the MID. Used to sign every request and callback.",
            ),
            CredentialField(
                key="website",
                label="Website",
                hint="Use WEBSTAGING for staging and DEFAULT (or your configured name) for live.",
                secret=False,
                default="WEBSTAGING",
                placeholder="WEBSTAGING",
            ),
        ),
        capabilities=("UPI intent", "UPI QR", "Cards", "Netbanking", "Paytm wallet", "Postpaid", "EMI"),
        webhook_events=("Payment success callback", "Payment failure callback"),
        webhook_notes="Add this URL as the Webhook URL in the Paytm dashboard. The per-order callback URL returns the buyer to the status page.",
    )

    def _base(self, mode: str) -> str:
        return SANDBOX_BASE if mode != "production" else PROD_BASE

    def _sign(self, payload: Dict[str, Any], key: str) -> str:
        return _checksum_module().generateSignature(json.dumps(payload), key)

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
            "requestType": "Payment",
            "mid": credentials["mid"],
            "websiteName": credentials.get("website") or "WEBSTAGING",
            "orderId": order.order_ref,
            "callbackUrl": return_url,
            "txnAmount": {
                "value": f"{order.amount_paise / 100:.2f}",
                "currency": "INR",
            },
            "userInfo": {
                "custId": str(user.id)[:32],
            },
        }
        signature = self._sign(body, credentials["merchant_key"])
        url = (
            f"{self._base(order.mode)}/theia/api/v1/initiateTransaction"
            f"?mid={credentials['mid']}&orderId={order.order_ref}"
        )
        async with httpx.AsyncClient(timeout=20.0) as client:
            res = await client.post(
                url,
                json={"body": body},
                headers={"Content-Type": "application/json", "signature": signature},
            )
        if res.status_code >= 400:
            raise PaymentDriverError(
                f"Paytm rejected the order ({res.status_code}): {res.text[:300]}"
            )
        data = res.json()
        token = (data.get("body") or {}).get("txnToken")
        if not token:
            raise PaymentDriverError(
                f"Paytm did not return a transaction token: {data.get('body', {}).get('resultInfo')}"
            )
        return CheckoutResult(
            provider_order_id=order.order_ref,
            payment_url=f"{public_base.rstrip('/')}/api/v1/payments/checkout/paytm/{order.order_ref}",
            payload={
                "txn_token": token,
                "mid": credentials["mid"],
                "order_id": order.order_ref,
            },
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
        checksum = fields.pop("CHECKSUMHASH", "")
        if not checksum:
            raise SignatureError("Missing Paytm CHECKSUMHASH.")
        if not _checksum_module().verifySignature(
            fields, credentials["merchant_key"], checksum
        ):
            raise SignatureError("Invalid Paytm callback checksum.")

        order_ref = fields.get("ORDERID", "")
        state = fields.get("STATUS", "")
        amount = fields.get("TXNAMOUNT")
        event_id = f"{order_ref}:{fields.get('TXNID', '')}:{state}"
        status = "paid" if state == "TXN_SUCCESS" else (
            "failed" if state in ("TXN_FAILURE", "TXN_FAILED") else "ignored"
        )
        return WebhookResult(
            order_ref=order_ref,
            status=status,
            amount_paise=round(float(amount) * 100) if amount else None,
            event_id=event_id,
            event_type=state or "payment",
            provider_order_id=order_ref,
            provider_payment_id=fields.get("TXNID"),
            payment_method=(fields.get("PAYMENTMODE") or "").upper() or None,
            raw=fields,
        )

    async def fetch_status(
        self,
        *,
        order,
        credentials: Dict[str, str],
    ) -> StatusResult:
        body = {"mid": credentials["mid"], "orderId": order.order_ref}
        signature = self._sign(body, credentials["merchant_key"])
        async with httpx.AsyncClient(timeout=20.0) as client:
            res = await client.post(
                f"{self._base(order.mode)}/v3/order/status",
                json={"body": body},
                headers={"Content-Type": "application/json", "signature": signature},
            )
        if res.status_code >= 400:
            raise PaymentDriverError(f"Paytm status failed ({res.status_code}).")
        data = res.json()
        result = (data.get("body") or {}).get("resultInfo", {})
        state = result.get("resultStatus")
        status = "paid" if state == "TXN_SUCCESS" else (
            "failed" if state == "TXN_FAILURE" else "pending"
        )
        amount = (data.get("body") or {}).get("txnAmount")
        return StatusResult(
            status=status,
            amount_paise=round(float(amount) * 100) if amount else None,
            provider_payment_id=(data.get("body") or {}).get("txnId"),
            raw=data,
        )

    async def test_credentials(
        self,
        *,
        credentials: Dict[str, str],
        mode: str,
    ) -> str:
        body = {"mid": credentials["mid"], "orderId": "TEST" + hashlib.md5(
            credentials["mid"].encode()
        ).hexdigest()[:10]}
        signature = self._sign(body, credentials["merchant_key"])
        async with httpx.AsyncClient(timeout=20.0) as client:
            res = await client.post(
                f"{self._base(mode)}/v3/order/status",
                json={"body": body},
                headers={"Content-Type": "application/json", "signature": signature},
            )
        if res.status_code in (401, 403):
            raise PaymentDriverError("Paytm rejected the MID or Merchant Key.")
        if res.status_code >= 500:
            raise PaymentDriverError(f"Paytm test failed ({res.status_code}).")
        return "Paytm credentials accepted."

    def checkout_page(
        self,
        *,
        order,
        credentials: Dict[str, str],
        mode: str,
    ) -> Optional[str]:
        payload = order.provider_payload or {}
        token = payload.get("txn_token")
        if not token:
            return None
        return auto_post_page(
            "Paytm checkout",
            f"Paying ₹{order.amount_paise / 100:,.2f} for {order.plan_name or 'your plan'}.",
            f"{self._base(mode)}/theia/processTransaction",
            {
                "mid": payload.get("mid") or credentials["mid"],
                "orderId": payload.get("order_id") or order.order_ref,
                "txnToken": token,
            },
        )
