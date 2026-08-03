"""
╔══════════════════════════════════════════════════════════════════╗
║  VIDHYA BOT — Subscription & Billing Service                    ║
║  Provides: Free plan provisioning, PhonePe Payment Gateway      ║
║  integration, signature verification, and automatic plan sync.  ║
╚══════════════════════════════════════════════════════════════════╝
"""

import base64
import hashlib
import json
import logging
import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional, Tuple, Dict, Any

import httpx
import redis.asyncio as aioredis
from fastapi import HTTPException, status
from sqlalchemy import select, update, func
from sqlalchemy.orm import joinedload
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.plan import Plan
from app.models.user import User
from app.models.payment import Payment
from app.models.subscription import UserSubscription
from app.redis_client import RedisKeys

def get_ist_end_of_day_expiry(days_valid: int) -> datetime:
    ist_tz = timezone(timedelta(hours=5, minutes=30))
    now_ist = datetime.now(ist_tz)
    target = now_ist + timedelta(days=days_valid)
    return target.replace(hour=23, minute=59, second=59, microsecond=999999)

settings = get_settings()
logger = logging.getLogger("vidhya.subscription")

PHONEPE_SANDBOX_URL = "https://api-preprod.phonepe.com/apis/pg-sandbox/pg/v1/pay"
PHONEPE_PROD_URL = "https://api.phonepe.com/apis/hermes/pg/v1/pay"


class SubscriptionService:
    """Manages plans, provisions active subscriptions, and handles billing with PhonePe."""

    @staticmethod
    async def activate_free_plan(
        user_id: uuid.UUID,
        db: AsyncSession,
        redis: aioredis.Redis
    ) -> UserSubscription:
        """
        Provision the default 'free' plan for a user.
        Ensures strict single active subscription rule.
        """
        # 1. Fetch free plan from DB
        result = await db.execute(select(Plan).where(Plan.name == "free"))
        free_plan = result.scalar_one_or_none()
        
        if not free_plan:
            # Fallback if plans are not seeded yet (though seeded in Phase 1)
            free_plan = Plan(
                name="free",
                display_name="Free Tier",
                description="Default free plan",
                price_inr=0,
                validity_days=3650,  # Effectively lifetime
                messages_per_day=5,
                messages_per_month=50,
                max_conversations=3,
                max_active_conversations=1,
                conversation_timeout_min=30,
                max_context_messages=5,
                max_context_tokens=2000,
                max_response_tokens=512,
                memory_retention_days=7,
                summary_frequency=10
            )
            db.add(free_plan)
            await db.flush()
            
        # 2. Deactivate existing active subscriptions
        await db.execute(
            update(UserSubscription)
            .where(UserSubscription.user_id == user_id)
            .where(UserSubscription.status == "active")
            .values(status="expired", updated_at=datetime.now(timezone.utc))
        )
        
        # 3. Create new Free Subscription
        subscription = UserSubscription(
            user_id=user_id,
            plan_id=free_plan.id,
            payment_id=None,
            status="active",
            started_at=datetime.now(timezone.utc),
            expires_at=get_ist_end_of_day_expiry(free_plan.validity_days),
            plan_snapshot=free_plan.to_snapshot(),
            total_messages_used=0,
            total_tokens_consumed=0,
            total_conversations=0
        )
        db.add(subscription)
        await db.flush()
        
        # 4. Cache in Redis
        cache_key = RedisKeys.subscription_cache(str(user_id))
        await redis.set(cache_key, json.dumps(subscription.plan_limits), ex=3600)
        
        return subscription

    @classmethod
    async def admin_assign_plan(
        cls,
        user_id: uuid.UUID,
        plan_id: uuid.UUID,
        db: AsyncSession,
        redis: aioredis.Redis
    ) -> UserSubscription:
        """
        Manually assign a plan to a user (Admin only).
        Bypasses payment gateways and immediately activates the plan.
        """
        # 1. Fetch Plan details
        result = await db.execute(select(Plan).where(Plan.id == plan_id))
        plan = result.scalar_one_or_none()
        
        if not plan or not plan.is_active:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Plan not found or deactivated."
            )
            
        # 2. Deactivate existing active subscriptions
        await db.execute(
            update(UserSubscription)
            .where(UserSubscription.user_id == user_id)
            .where(UserSubscription.status == "active")
            .values(status="expired", updated_at=datetime.now(timezone.utc))
        )
        
        # 3. Create new Subscription
        subscription = UserSubscription(
            user_id=user_id,
            plan_id=plan.id,
            payment_id=None,
            status="active",
            started_at=datetime.now(timezone.utc),
            expires_at=get_ist_end_of_day_expiry(plan.validity_days),
            plan_snapshot=plan.to_snapshot(),
            total_messages_used=0,
            total_tokens_consumed=0,
            total_conversations=0
        )
        db.add(subscription)
        await db.flush()
        
        # 4. Clear cache to force reload quotas
        cache_key = RedisKeys.subscription_cache(str(user_id))
        await redis.delete(cache_key)
        
        # 5. Clear usage stats for the new period
        # Note: True reset logic depends on business rules, but deleting cache ensures they get the new plan immediately
        usage_cache_key = RedisKeys.quota_daily(str(user_id), datetime.now(timezone.utc).strftime("%Y-%m-%d"))
        await redis.delete(usage_cache_key)
        
        return subscription

    @staticmethod
    async def initiate_plan_purchase(
        user_id: uuid.UUID,
        plan_id: uuid.UUID,
        mobile_number: Optional[str],
        db: AsyncSession
    ) -> Tuple[Payment, str]:
        """
        Initiate purchase of a plan.
        Creates a Payment record and generates PhonePe payment payload & signature.
        
        Returns:
            Tuple[Payment, phonepe_redirect_url]
        """
        # 1. Fetch Plan details
        result = await db.execute(select(Plan).where(Plan.id == plan_id))
        plan = result.scalar_one_or_none()
        
        if not plan or not plan.is_active:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Plan not found or deactivated."
            )
            
        if plan.is_free:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot purchase free plan. Use free plan activation instead."
            )
            
        # 1.5 Prevent buying same or lower plan
        active_sub_result = await db.execute(
            select(UserSubscription)
            .options(joinedload(UserSubscription.plan))
            .where(UserSubscription.user_id == user_id)
            .where(UserSubscription.status == "active")
        )
        active_sub = active_sub_result.scalar_one_or_none()
        
        if active_sub and not active_sub.plan.is_free:
            if active_sub.plan_id == plan.id:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"You already have the {plan.display_name} active."
                )
            if active_sub.plan.price_inr > plan.price_inr:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"You currently have a higher tier plan ({active_sub.plan.display_name}). Downgrading is not permitted via this flow."
                )
            
        # 2. Create Payment Record (Amount in Paise)
        merchant_txn_id = f"TXN-{uuid.uuid4().hex[:20].upper()}"
        amount_paise = plan.price_inr * 100
        
        payment = Payment(
            user_id=user_id,
            plan_id=plan.id,
            merchant_txn_id=merchant_txn_id,
            amount_inr=amount_paise,
            currency="INR",
            status="initiated",
            initiated_at=datetime.now(timezone.utc)
        )
        db.add(payment)
        await db.flush()
        
        # 3. Formulate PhonePe API payload
        payload = {
            "merchantId": settings.PHONEPE_MERCHANT_ID,
            "merchantTransactionId": merchant_txn_id,
            "merchantUserId": f"USER-{str(user_id)[:20].upper()}",
            "amount": amount_paise,
            "redirectUrl": f"{settings.PHONEPE_REDIRECT_URL}?txn_id={merchant_txn_id}",
            "redirectMode": "REDIRECT",
            "callbackUrl": settings.PHONEPE_CALLBACK_URL,
            "paymentInstrument": {"type": "PAY_PAGE"}
        }
        if mobile_number:
            payload["mobileNumber"] = mobile_number
            
        # Base64 encode the payload
        payload_bytes = json.dumps(payload).encode("utf-8")
        payload_base64 = base64.b64encode(payload_bytes).decode("utf-8")
        
        # Compute signature: SHA256(Base64_Payload + "/pg/v1/pay" + Salt_Key) + "###" + Salt_Index
        salt_key = settings.PHONEPE_SALT_KEY
        salt_index = settings.PHONEPE_SALT_INDEX
        
        sign_string = payload_base64 + "/pg/v1/pay" + salt_key
        sha256_hash = hashlib.sha256(sign_string.encode("utf-8")).hexdigest()
        x_verify = f"{sha256_hash}###{salt_index}"
        
        # 4. Trigger HTTP call to PhonePe
        pg_url = PHONEPE_SANDBOX_URL if settings.PHONEPE_ENV == "sandbox" else PHONEPE_PROD_URL
        headers = {
            "Content-Type": "application/json",
            "X-VERIFY": x_verify,
            "accept": "application/json"
        }
        req_body = {"request": payload_base64}
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(pg_url, json=req_body, headers=headers, timeout=15.0)
                res_data = response.json()
        except Exception as e:
            payment.status = "failed"
            payment.response_data = {"error": f"Failed to connect to PhonePe: {str(e)}"}
            await db.commit()
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"PhonePe Gateway connection failed: {str(e)}"
            )
            
        # 5. Handle response and redirect URL
        payment.response_data = res_data
        
        if res_data.get("success") is True and res_data.get("code") in ("SUCCESS", "PAYMENT_INITIATED"):
            instrument_resp = res_data.get("data", {}).get("instrumentResponse", {})
            redirect_url = instrument_resp.get("redirectInfo", {}).get("url")
            
            if redirect_url:
                return payment, redirect_url
                
        payment.status = "failed"
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"PhonePe purchase initiation failed: {res_data.get('message', 'Unknown Error')}"
        )

    @classmethod
    async def handle_phonepe_webhook(
        cls,
        payload_base64: str,
        x_verify: str,
        db: AsyncSession,
        redis: aioredis.Redis
    ) -> bool:
        """
        Validate and process the incoming PhonePe webhook callback.
        On success, deactivates older plans and provisions/enables subscription.
        """
        # 1. Signature check
        salt_key = settings.PHONEPE_SALT_KEY
        salt_index = settings.PHONEPE_SALT_INDEX
        
        sign_string = payload_base64 + salt_key
        sha256_hash = hashlib.sha256(sign_string.encode("utf-8")).hexdigest()
        computed_verify = f"{sha256_hash}###{salt_index}"
        
        # Verify header signature
        if computed_verify != x_verify:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid webhook signature."
            )
                
        # 2. Decode payload
        try:
            decoded_bytes = base64.b64decode(payload_base64)
            webhook_data = json.loads(decoded_bytes.decode("utf-8"))
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Failed to decode webhook payload: {str(e)}"
            )
            
        # 3. Retrieve payment record
        success_code = webhook_data.get("success")
        code = webhook_data.get("code")
        data = webhook_data.get("data", {})
        merchant_txn_id = data.get("merchantTransactionId")
        
        if not merchant_txn_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Missing merchant transaction ID in webhook payload."
            )
            
        result = await db.execute(select(Payment).where(Payment.merchant_txn_id == merchant_txn_id))
        payment = result.scalar_one_or_none()
        
        if not payment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Payment transaction {merchant_txn_id} not found."
            )
            
        # If transaction was already processed, ignore repeat hook
        if payment.status in ("success", "failed"):
            return True
            
        # 4. Process Payment Result
        payment.phonepe_txn_id = data.get("transactionId")
        payment.payment_method = data.get("paymentInstrument", {}).get("type")
        payment.payment_instrument = data.get("paymentInstrument")
        payment.response_data = webhook_data
        payment.completed_at = datetime.now(timezone.utc)
        
        if success_code is True and code == "PAYMENT_SUCCESS":
            payment.status = "success"
            
            logger.info(f"Payment SUCCESS: txn={merchant_txn_id}, user_id={payment.user_id}, plan_id={payment.plan_id}")
            
            # Retrieve user and plan
            plan_result = await db.execute(select(Plan).where(Plan.id == payment.plan_id))
            plan = plan_result.scalar_one()
            
            # PREVENT DELAYED WEBHOOK DOWNGRADES
            # If the user already has an active plan that is more expensive, do NOT downgrade them.
            active_sub_result = await db.execute(
                select(UserSubscription)
                .options(joinedload(UserSubscription.plan))
                .where(UserSubscription.user_id == payment.user_id)
                .where(UserSubscription.status == "active")
            )
            active_sub = active_sub_result.scalar_one_or_none()
            
            if active_sub and not active_sub.plan.is_free:
                if active_sub.plan.price_inr > plan.price_inr:
                    logger.warning(f"Prevented downgrade via delayed webhook! User {payment.user_id} has {active_sub.plan.name} (₹{active_sub.plan.price_inr}), ignored incoming {plan.name} (₹{plan.price_inr}) activation.")
                    # Keep the payment as success, but do NOT provision the lower plan.
                    await db.commit()
                    return True
                
                if active_sub.plan_id == plan.id:
                    logger.info(f"User {payment.user_id} bought {plan.name} again. Renewing validity.")
            
            # Deactivate previous active plans
            await db.execute(
                update(UserSubscription)
                .where(UserSubscription.user_id == payment.user_id)
                .where(UserSubscription.status == "active")
                .values(status="cancelled", updated_at=datetime.now(timezone.utc))
            )
            
            # Provision active subscription
            subscription = UserSubscription(
                user_id=payment.user_id,
                plan_id=plan.id,
                payment_id=payment.id,
                status="active",
                started_at=datetime.now(timezone.utc),
                expires_at=get_ist_end_of_day_expiry(plan.validity_days),
                plan_snapshot=plan.to_snapshot(),
                total_messages_used=0,
                total_tokens_consumed=0,
                total_conversations=0
            )
            db.add(subscription)
            await db.flush()
            
            # Evict from Cache and refresh Redis
            cache_key = RedisKeys.subscription_cache(str(payment.user_id))
            await redis.set(cache_key, json.dumps(subscription.plan_limits), ex=3600)
            
            # Retrieve User to get Telegram ID
            user_result = await db.execute(select(User).where(User.id == payment.user_id))
            user = user_result.scalar_one_or_none()
            
            if user and user.telegram_id and settings.TELEGRAM_BOT_TOKEN:
                import asyncio
                amount_rupees = payment.amount_inr / 100
                upi_ref = payment.phonepe_txn_id or merchant_txn_id
                
                message = (
                    "🎉 *Payment Successful!* 🌟\n\n"
                    f"Thank you for upgrading to *{plan.display_name}*.\n"
                    f"Amount Paid: *₹{amount_rupees:.2f}*\n"
                    f"Transaction Ref: `{upi_ref}`\n\n"
                    "Your new plan is now active! Enjoy your premium features. 🚀"
                )
                
                async def send_tg_msg():
                    try:
                        async with httpx.AsyncClient() as client:
                            await client.post(
                                f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/sendMessage",
                                json={
                                    "chat_id": user.telegram_id,
                                    "text": message,
                                    "parse_mode": "Markdown"
                                }
                            )
                    except Exception as e:
                        from app.main import logger
                        logger.error(f"Failed to send Telegram payment notification: {e}")
                
                asyncio.create_task(send_tg_msg())
            
            
        else:
            payment.status = "failed"
            logger.warning(f"Payment FAILED: txn={merchant_txn_id}, code={code}, success={success_code}")
            
        await db.commit()
        return True
