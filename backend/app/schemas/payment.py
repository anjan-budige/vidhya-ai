"""Vidhya AI — Payment schemas."""

import uuid
from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel

from app.schemas.base import VidhyaBaseModel


class PaymentInitiateRequest(BaseModel):
    plan_id: uuid.UUID
    idempotency_key: Optional[str] = None


class PaymentInitiateResponse(VidhyaBaseModel):
    merchant_txn_id: str
    order_ref: str
    payment_url: str
    amount_inr: int  # paise, kept for the existing clients
    amount_paise: int
    plan_name: str
    expires_in_seconds: int = 900
    mode: str
    provider: str
    is_test: bool


class PaymentVerifyResponse(VidhyaBaseModel):
    merchant_txn_id: str
    order_ref: str
    status: str  # success | failed | pending
    order_status: str
    amount_inr: int
    plan_name: Optional[str] = None
    subscription_activated: bool = False
    mode: Optional[str] = None
    provider: Optional[str] = None
    is_test: bool = False


class PaymentHistoryResponse(VidhyaBaseModel):
    id: uuid.UUID
    merchant_txn_id: str
    order_ref: str
    provider_transaction_id: Optional[str] = None
    phonepe_txn_id: Optional[str] = None  # legacy clients; always null now
    amount_inr: int
    currency: str = "INR"
    status: str
    order_status: str
    payment_method: Optional[str] = None
    plan_name: Optional[str] = None
    provider: Optional[str] = None
    mode: Optional[str] = None
    is_test: bool = False
    initiated_at: datetime
    completed_at: Optional[datetime] = None
    created_at: datetime


class AdminPaymentHistoryResponse(PaymentHistoryResponse):
    user_email: Optional[str] = None
    user_name: Optional[str] = None


class DemoCompleteRequest(BaseModel):
    result: Literal["success", "failed"]
