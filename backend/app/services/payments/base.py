"""Common types and interfaces for payment drivers."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple


@dataclass(frozen=True)
class CredentialField:
    key: str
    label: str
    hint: str = ""
    secret: bool = True
    placeholder: str = ""
    default: str = ""
    required: bool = True


@dataclass(frozen=True)
class ProviderMeta:
    driver: str
    name: str
    tagline: str
    brand_slug: str
    brand_color: str
    docs_url: str
    fields: Tuple[CredentialField, ...]
    capabilities: Tuple[str, ...]
    webhook_events: Tuple[str, ...] = ()
    webhook_notes: str = ""
    modes: Tuple[str, ...] = ("sandbox", "production")


@dataclass
class CheckoutResult:
    provider_order_id: str
    payment_url: str
    payload: Dict[str, Any] = field(default_factory=dict)


@dataclass
class WebhookResult:
    order_ref: str
    status: str  # paid | failed | ignored
    amount_paise: Optional[int] = None
    event_id: str = ""
    event_type: str = "payment"
    provider_order_id: Optional[str] = None
    provider_payment_id: Optional[str] = None
    payment_method: Optional[str] = None
    raw: Dict[str, Any] = field(default_factory=dict)


@dataclass
class StatusResult:
    status: str  # paid | failed | pending
    amount_paise: Optional[int] = None
    provider_payment_id: Optional[str] = None
    raw: Dict[str, Any] = field(default_factory=dict)


class PaymentDriverError(Exception):
    """Internal provider failure with an optional admin-safe explanation."""

    def __init__(self, message: str, safe_message: str | None = None):
        super().__init__(message)
        self.safe_message = safe_message


class SignatureError(PaymentDriverError):
    pass


class PaymentDriver(ABC):
    meta: ProviderMeta

    def required_keys(self) -> List[str]:
        return [f.key for f in self.meta.fields if f.required]

    def validate_credentials(self, credentials: Dict[str, Any]) -> List[str]:
        missing = [
            f.label
            for f in self.meta.fields
            if f.required and not str(credentials.get(f.key, "")).strip()
        ]
        return missing

    def normalize_credentials(
        self, credentials: Dict[str, Any]
    ) -> Dict[str, str]:
        out: Dict[str, str] = {}
        for f in self.meta.fields:
            value = credentials.get(f.key)
            if value is None or str(value).strip() == "":
                if f.default:
                    out[f.key] = f.default
                continue
            out[f.key] = str(value).strip()
        return out

    @abstractmethod
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
        raise NotImplementedError

    @abstractmethod
    def verify_webhook(
        self,
        *,
        credentials: Dict[str, str],
        headers: Dict[str, str],
        raw_body: bytes,
        config: Optional[Dict[str, Any]] = None,
    ) -> WebhookResult:
        raise NotImplementedError

    @abstractmethod
    async def fetch_status(
        self,
        *,
        order,
        credentials: Dict[str, str],
    ) -> StatusResult:
        raise NotImplementedError

    @abstractmethod
    async def test_credentials(
        self,
        *,
        credentials: Dict[str, str],
        mode: str,
    ) -> str:
        """Return a short success message or raise PaymentDriverError."""
        raise NotImplementedError

    def checkout_page(
        self,
        *,
        order,
        credentials: Dict[str, str],
        mode: str,
    ) -> Optional[str]:
        return None
