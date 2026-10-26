"""Local demo driver — no provider, no real money."""

from typing import Any, Dict, Optional

from app.services.payments.base import (
    CheckoutResult,
    PaymentDriver,
    ProviderMeta,
    StatusResult,
    WebhookResult,
)


class DemoDriver(PaymentDriver):
    meta = ProviderMeta(
        driver="demo",
        name="Demo checkout",
        tagline="Test the full payment flow with no gateway account and no real money.",
        brand_slug="demo",
        brand_color="#4680FF",
        docs_url="",
        fields=(),
        capabilities=("Simulated checkout", "Instant success/failure", "No credentials"),
        modes=("demo",),
    )

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
        return CheckoutResult(
            provider_order_id=f"demo_{order.order_ref}",
            payment_url=f"{public_base.rstrip('/')}/api/v1/payments/demo/{order.order_ref}",
            payload={"simulated": True},
        )

    def verify_webhook(
        self,
        *,
        credentials: Dict[str, str],
        headers: Dict[str, str],
        raw_body: bytes,
        config: Optional[Dict[str, Any]] = None,
    ) -> WebhookResult:
        return WebhookResult(order_ref="", status="ignored")

    async def fetch_status(
        self,
        *,
        order,
        credentials: Dict[str, str],
    ) -> StatusResult:
        return StatusResult(
            status="paid" if order.status == "paid" else "pending",
            amount_paise=order.amount_paise,
        )

    async def test_credentials(
        self,
        *,
        credentials: Dict[str, str],
        mode: str,
    ) -> str:
        return "Demo mode is ready — no credentials needed."
