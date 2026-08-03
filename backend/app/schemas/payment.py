"""Vidhya Bot — Payment Schemas"""

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

from app.schemas.base import VidhyaBaseModel


class PaymentInitiateRequest(BaseModel):
    """Initiate a payment for a plan."""
    plan_id: uuid.UUID


class PaymentInitiateResponse(VidhyaBaseModel):
    """Response with PhonePe payment link."""
    merchant_txn_id: str
    payment_url: str
    amount_inr: int  # in paise
    plan_name: str
    expires_in_seconds: int = 900  # 15 min


class PaymentWebhookPayload(BaseModel):
    """PhonePe webhook callback payload."""
    response: str  # Base64 encoded
    # PhonePe sends X-VERIFY header for signature validation


class PaymentVerifyResponse(VidhyaBaseModel):
    """Payment verification response."""
    merchant_txn_id: str
    status: str
    amount_inr: int
    plan_name: Optional[str] = None
    subscription_activated: bool = False


class PaymentHistoryResponse(VidhyaBaseModel):
    """Payment record in history list."""
    id: uuid.UUID
    merchant_txn_id: str
    phonepe_txn_id: Optional[str] = None
    amount_inr: int
    currency: str = "INR"
    status: str
    payment_method: Optional[str] = None
    plan_name: Optional[str] = None
    initiated_at: datetime
    completed_at: Optional[datetime] = None
    created_at: datetime


class AdminPaymentHistoryResponse(PaymentHistoryResponse):
    """Payment record with user details for admin."""
    user_email: str
    user_name: Optional[str] = None
