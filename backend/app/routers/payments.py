"""
╔══════════════════════════════════════════════════════════════════╗
║  VIDHYA BOT — Payments Router                                    ║
║  Provides: PhonePe billing checkouts, webhook notifications, and ║
║  user billing transaction listings.                              ║
╚══════════════════════════════════════════════════════════════════╝
"""

import logging
import uuid
from typing import List, Optional

import redis.asyncio as aioredis
from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db, get_redis_client, get_current_user, require_superadmin
from app.models.payment import Payment
from app.models.plan import Plan
from app.models.user import User
from app.models.audit_log import AuditLog
from app.services.subscription import SubscriptionService
from app.schemas.payment import (
    PaymentInitiateRequest,
    PaymentInitiateResponse,
    PaymentWebhookPayload,
    PaymentHistoryResponse,
    PaymentVerifyResponse,
    AdminPaymentHistoryResponse
)
from app.schemas.auth import CurrentUser, CurrentAdmin

logger = logging.getLogger("vidhya.payments")

router = APIRouter(prefix="/payments", tags=["Payments / Billing"])


@router.post("/initiate", response_model=PaymentInitiateResponse, status_code=status.HTTP_201_CREATED)
async def initiate_payment(
    payload: PaymentInitiateRequest,
    request: Request,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Initiate a subscription plan purchase transaction.
    Returns PhonePe checkout redirect URL.
    """
    # Verify user profile mobile number or fetch from DB
    result = await db.execute(select(User).where(User.id == current_user.id))
    user = result.scalar_one()
    
    # Generate merchant payload and post request to PhonePe PG
    payment, redirect_url = await SubscriptionService.initiate_plan_purchase(
        user_id=current_user.id,
        plan_id=payload.plan_id,
        mobile_number=None,  # Standard checkout uses redirect flow, can be mapped from metadata
        db=db
    )
    
    await db.commit()
    
    logger.info(
        f"Payment INITIATED: txn={payment.merchant_txn_id}, "
        f"user_id={current_user.id}, telegram_id={current_user.telegram_id}, "
        f"plan_id={payload.plan_id}"
    )
    
    # Retrieve target plan name
    plan_result = await db.execute(select(Plan).where(Plan.id == payload.plan_id))
    plan = plan_result.scalar_one()
    
    # Audit log for payment initiation
    db.add(AuditLog(
        admin_id=None,
        action="payment.initiated",
        resource_type="payment",
        resource_id=payment.id,
        details={
            "user_id": str(current_user.id),
            "plan": plan.name,
            "amount_inr": payment.amount_inr,
            "merchant_txn_id": payment.merchant_txn_id
        }
    ))
    await db.commit()
    
    return PaymentInitiateResponse(
        merchant_txn_id=payment.merchant_txn_id,
        payment_url=redirect_url,
        amount_inr=payment.amount_inr,
        plan_name=plan.name,
        expires_in_seconds=900  # 15 minutes TTL on checkout
    )


@router.post("/webhook", status_code=status.HTTP_200_OK)
async def phonepe_payment_webhook(
    payload: PaymentWebhookPayload,
    x_verify: str = Header(..., description="PhonePe signature checksum header"),
    db: AsyncSession = Depends(get_db),
    redis: aioredis.Redis = Depends(get_redis_client)
):
    """
    PhonePe server callback notification webhook.
    Validates payload integrity and provisions plan subscription.
    """
    success = await SubscriptionService.handle_phonepe_webhook(
        payload_base64=payload.response,
        x_verify=x_verify,
        db=db,
        redis=redis
    )
    
    # PhonePe webhook expects a successful acknowledgment
    if success:
        # Audit log for successful payment
        db.add(AuditLog(
            admin_id=None,
            action="payment.success",
            resource_type="payment",
            resource_id=None,
            details={"source": "phonepe_webhook"}
        ))
        await db.commit()
        return {"status": "SUCCESS", "message": "Webhook processed successfully"}
        
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Webhook processing failed."
    )


@router.get("/check/{merchant_txn_id}", response_model=PaymentVerifyResponse, status_code=status.HTTP_200_OK)
async def check_payment_status(
    merchant_txn_id: str,
    db: AsyncSession = Depends(get_db)
):
    """
    Public endpoint for payment status page to check if a payment succeeded.
    No auth required — the merchant_txn_id is a unique, unguessable UUID.
    """
    result = await db.execute(
        select(Payment).where(Payment.merchant_txn_id == merchant_txn_id)
    )
    payment = result.scalar_one_or_none()

    if not payment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Payment transaction not found."
        )

    # Load plan name
    plan_name = None
    if payment.plan_id:
        plan_result = await db.execute(select(Plan).where(Plan.id == payment.plan_id))
        plan = plan_result.scalar_one_or_none()
        plan_name = plan.display_name if plan else None

    return PaymentVerifyResponse(
        merchant_txn_id=payment.merchant_txn_id,
        status=payment.status,
        amount_inr=payment.amount_inr,
        plan_name=plan_name,
        subscription_activated=payment.status == "success"
    )


@router.get("/history", response_model=List[PaymentHistoryResponse], status_code=status.HTTP_200_OK)
async def get_payment_history(
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Retrieve paginated user payment checkout histories.
    """
    result = await db.execute(
        select(Payment)
        .where(Payment.user_id == current_user.id)
        .order_by(Payment.created_at.desc())
    )
    payments = result.scalars().all()
    
    response_list = []
    for pay in payments:
        # Load associated plan details
        plan_result = await db.execute(select(Plan).where(Plan.id == pay.plan_id))
        plan = plan_result.scalar_one_or_none()
        plan_name = plan.display_name if plan else "Unknown Plan"
        
        response_list.append(
            PaymentHistoryResponse(
                id=pay.id,
                merchant_txn_id=pay.merchant_txn_id,
                phonepe_txn_id=pay.phonepe_txn_id,
                amount_inr=pay.amount_inr,
                currency=pay.currency,
                status=pay.status,
                payment_method=pay.payment_method,
                plan_name=plan_name,
                initiated_at=pay.initiated_at,
                completed_at=pay.completed_at,
                created_at=pay.created_at
            )
        )
        
        
    return response_list


@router.get("/all", response_model=List[AdminPaymentHistoryResponse], status_code=status.HTTP_200_OK)
async def get_all_payments(
    current_admin: CurrentAdmin = Depends(require_superadmin),
    db: AsyncSession = Depends(get_db)
):
    """
    Retrieve paginated user payment checkout histories across all users (Superadmin only).
    """
    result = await db.execute(
        select(Payment, User, Plan)
        .outerjoin(User, Payment.user_id == User.id)
        .outerjoin(Plan, Payment.plan_id == Plan.id)
        .order_by(Payment.created_at.desc())
    )
    rows = result.all()
    
    response_list = []
    for pay, user, plan in rows:
        plan_name = plan.display_name if plan else "Unknown Plan"
        
        response_list.append(
            AdminPaymentHistoryResponse(
                id=pay.id,
                merchant_txn_id=pay.merchant_txn_id,
                phonepe_txn_id=pay.phonepe_txn_id,
                amount_inr=pay.amount_inr,
                currency=pay.currency,
                status=pay.status,
                payment_method=pay.payment_method,
                plan_name=plan_name,
                initiated_at=pay.initiated_at,
                completed_at=pay.completed_at,
                created_at=pay.created_at,
                user_email=user.telegram_username or str(user.telegram_id) if user else "Unknown User",
                user_name=user.first_name if user else None
            )
        )
        
    return response_list
