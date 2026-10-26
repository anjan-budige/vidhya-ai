"""
Vidhya Bot — Web Authentication Service

Email + password accounts with email OTP verification. Identity lives in
Postgres; sessions live in Redis. Telegram users share the same table.
"""

import hashlib
import hmac
import re
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional, Tuple

import redis.asyncio as aioredis
from fastapi import HTTPException, status
from sqlalchemy import delete, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.email_otp import EmailOTP
from app.models.session import Session as UserSession
from app.models.user import User
from app.models.user_api_key import UserApiKey
from app.redis_client import RedisKeys
from app.services.auth import AdminAuthService
from app.services.platform import PlatformConfigService
from app.utils.email import (
    send_account_created_email,
    send_otp_email,
    send_user_reset_password_email,
)

settings = get_settings()

OTP_TTL_MINUTES = 10
OTP_MAX_ATTEMPTS = 5
OTP_RESEND_COOLDOWN = 60
OTP_MAX_PER_HOUR = 3
LOGIN_MAX_ATTEMPTS = 5
LOGIN_LOCKOUT_MINUTES = 15
SESSION_DAYS = 30
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _normalise(value: str) -> str:
    return (value or "").strip().lower()


def _split_name(name: str) -> Tuple[str, Optional[str]]:
    parts = (name or "").strip().split(" ", 1)
    return parts[0] or "Learner", (parts[1] if len(parts) > 1 else None)


def _hash_code(otp_id, code: str) -> str:
    return hmac.new(
        settings.SECRET_KEY.encode("utf-8"),
        f"{otp_id}:{code}".encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


class WebAuthService:

    @classmethod
    async def revoke_user_sessions(
        cls,
        db: AsyncSession,
        redis: aioredis.Redis,
        user_id: uuid.UUID,
        revoke_api_keys: bool = False,
    ) -> None:
        """Invalidate every browser session, and optionally all API keys."""
        user_id_str = str(user_id)
        async for key in redis.scan_iter(match="session:*", count=200):
            if await redis.hget(key, "user_id") == user_id_str:
                await redis.delete(key)

        await db.execute(
            delete(UserSession).where(UserSession.user_id == user_id)
        )

        keys = (
            await db.execute(
                select(UserApiKey).where(UserApiKey.user_id == user_id)
            )
        ).scalars().all()
        for api_key in keys:
            await redis.delete(f"apikey:{api_key.key_hash}")
            if revoke_api_keys:
                api_key.is_enabled = False


    @staticmethod
    async def _find_user(db: AsyncSession, identifier: str) -> Optional[User]:
        ident = _normalise(identifier)
        result = await db.execute(
            select(User).where(
                or_(User.username == ident, User.email == ident)
            )
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def _assert_available(
        db: AsyncSession, username: str, email: str, mobile: str
    ) -> None:
        result = await db.execute(
            select(User).where(
                or_(
                    User.username == username,
                    User.email == email,
                    User.mobile == mobile,
                )
            )
        )
        existing = result.scalar_one_or_none()
        if not existing:
            return
        if existing.username == username:
            raise HTTPException(409, "That username is already taken.")
        if existing.email == email:
            raise HTTPException(409, "An account with that email already exists.")
        raise HTTPException(409, "An account with that mobile number already exists.")


    @classmethod
    async def issue_otp(
        cls, db: AsyncSession, user: User, purpose: str
    ) -> str:
        if not user.email:
            raise HTTPException(400, "This account has no email address.")

        now = datetime.now(timezone.utc)
        recent_count = (
            await db.execute(
                select(func.count())
                .select_from(EmailOTP)
                .where(
                    EmailOTP.user_id == user.id,
                    EmailOTP.purpose == purpose,
                    EmailOTP.created_at >= now - timedelta(hours=1),
                )
            )
        ).scalar() or 0
        if recent_count >= OTP_MAX_PER_HOUR:
            raise HTTPException(429, "Too many codes requested. Try again later.")

        latest = (
            await db.execute(
                select(EmailOTP)
                .where(
                    EmailOTP.user_id == user.id,
                    EmailOTP.purpose == purpose,
                )
                .order_by(EmailOTP.created_at.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        if latest and latest.created_at > now - timedelta(seconds=OTP_RESEND_COOLDOWN):
            raise HTTPException(429, "Please wait a minute before requesting another code.")

        await db.execute(
            update(EmailOTP)
            .where(
                EmailOTP.user_id == user.id,
                EmailOTP.purpose == purpose,
                EmailOTP.consumed_at.is_(None),
            )
            .values(consumed_at=now)
        )

        otp_id = uuid.uuid4()
        code = f"{secrets.randbelow(1_000_000):06d}"
        db.add(
            EmailOTP(
                id=otp_id,
                user_id=user.id,
                purpose=purpose,
                code_hash=_hash_code(otp_id, code),
                expires_at=now + timedelta(minutes=OTP_TTL_MINUTES),
            )
        )
        await db.flush()
        return code

    @classmethod
    async def _consume_otp(
        cls, db: AsyncSession, user: User, purpose: str, code: str
    ) -> None:
        now = datetime.now(timezone.utc)
        otp = (
            await db.execute(
                select(EmailOTP)
                .where(
                    EmailOTP.user_id == user.id,
                    EmailOTP.purpose == purpose,
                    EmailOTP.consumed_at.is_(None),
                )
                .order_by(EmailOTP.created_at.desc())
                .limit(1)
            )
        ).scalar_one_or_none()

        if not otp or otp.expires_at < now:
            raise HTTPException(400, "Invalid or expired code.")
        if otp.attempts >= OTP_MAX_ATTEMPTS:
            raise HTTPException(429, "Too many attempts. Request a new code.")

        if not hmac.compare_digest(otp.code_hash, _hash_code(otp.id, code)):
            otp.attempts += 1
            await db.commit()
            raise HTTPException(400, "Invalid or expired code.")

        otp.consumed_at = now


    @classmethod
    async def create_session(
        cls,
        db: AsyncSession,
        redis: aioredis.Redis,
        user: User,
        ip_address: Optional[str] = None,
        device_info: Optional[dict] = None,
        method: str = "password",
    ) -> Tuple[str, datetime]:
        now = datetime.now(timezone.utc)
        token = f"usess_{uuid.uuid4().hex}"
        expires_at = now + timedelta(days=SESSION_DAYS)

        db.add(
            UserSession(
                user_id=user.id,
                session_token=token,
                device_info={**(device_info or {}), "auth_method": method},
                ip_address=ip_address,
                expires_at=expires_at,
                is_active=True,
            )
        )

        await redis.hset(
            RedisKeys.session(token),
            mapping={
                "user_id": str(user.id),
                "telegram_id": str(user.telegram_id or ""),
                "username": user.username or user.telegram_username or "",
                "auth_method": method,
            },
        )
        await redis.expire(RedisKeys.session(token), SESSION_DAYS * 24 * 3600)
        user.last_login_at = now
        return token, expires_at


    @classmethod
    async def register(
        cls, db: AsyncSession, redis: aioredis.Redis, payload: Any
    ) -> User:
        access = await PlatformConfigService.get_access_settings(db, redis)
        if not access["registration_enabled"]:
            raise HTTPException(
                403, "Public registration is disabled. Ask an administrator for an account."
            )

        username = _normalise(payload.username)
        email = _normalise(payload.email)
        mobile = re.sub(r"[\s-]+", "", payload.mobile)

        if not EMAIL_RE.match(email):
            raise HTTPException(422, "Enter a valid email address.")

        await cls._assert_available(db, username, email, mobile)
        first_name, last_name = _split_name(payload.name)

        user = User(
            username=username,
            email=email,
            mobile=mobile,
            password_hash=AdminAuthService.hash_password(payload.password),
            auth_provider="web",
            first_name=first_name,
            last_name=last_name,
            is_active=True,
            is_banned=False,
            telegram_id=None,
        )
        db.add(user)
        await db.flush()

        code = await cls.issue_otp(db, user, "verify_email")
        await db.commit()

        await send_otp_email(email, first_name, code, "verify_email")
        return user

    @classmethod
    async def verify_email(
        cls,
        db: AsyncSession,
        redis: aioredis.Redis,
        identifier: str,
        code: str,
        ip_address: Optional[str] = None,
        device_info: Optional[dict] = None,
    ) -> Tuple[User, str, datetime]:
        user = await cls._find_user(db, identifier)
        if not user:
            raise HTTPException(400, "Invalid or expired code.")

        await cls._consume_otp(db, user, "verify_email", code)
        user.email_verified_at = user.email_verified_at or datetime.now(timezone.utc)
        token, expires_at = await cls.create_session(
            db, redis, user, ip_address, device_info, method="email_verify"
        )
        await db.commit()
        return user, token, expires_at

    @classmethod
    async def resend_verification(
        cls, db: AsyncSession, redis: aioredis.Redis, identifier: str
    ) -> None:
        user = await cls._find_user(db, identifier)
        if not user or user.email_verified_at or not user.email:
            return  # Do not reveal whether the account exists.

        code = await cls.issue_otp(db, user, "verify_email")
        await db.commit()
        await send_otp_email(user.email, user.first_name, code, "verify_email")


    @classmethod
    async def login(
        cls,
        db: AsyncSession,
        redis: aioredis.Redis,
        identifier: str,
        password: str,
        ip_address: Optional[str] = None,
        device_info: Optional[dict] = None,
    ) -> Dict[str, Any]:
        ident = _normalise(identifier)
        lock_key = f"ratelimit:userlogin:{ident}"
        failed = await redis.get(lock_key)
        if failed and int(failed) >= LOGIN_MAX_ATTEMPTS:
            raise HTTPException(
                423, "Too many failed attempts. Try again in 15 minutes."
            )

        user = await cls._find_user(db, identifier)
        valid = bool(
            user
            and user.password_hash
            and AdminAuthService.verify_password(password, user.password_hash)
        )
        if not valid:
            count = await redis.incr(lock_key)
            if count == 1:
                await redis.expire(lock_key, LOGIN_LOCKOUT_MINUTES * 60)
            raise HTTPException(401, "Invalid username or password.")

        await redis.delete(lock_key)

        if user.is_banned:
            raise HTTPException(403, f"Account banned: {user.ban_reason or 'Contact support.'}")
        if not user.is_active:
            raise HTTPException(403, "Account is deactivated.")
        if user.auth_provider in ("web", "admin") and not user.email_verified_at:
            raise HTTPException(403, "Verify your email before signing in.")

        access = await PlatformConfigService.get_access_settings(db, redis)
        if access["email_otp_login"]:
            code = await cls.issue_otp(db, user, "login")
            otp_token = uuid.uuid4().hex
            await redis.set(f"login_pending:{otp_token}", str(user.id), ex=600)
            await db.commit()
            await send_otp_email(user.email, user.first_name, code, "login")
            return {"requires_otp": True, "otp_token": otp_token, "user": user}

        token, expires_at = await cls.create_session(
            db, redis, user, ip_address, device_info, method="password"
        )
        await db.commit()
        return {
            "requires_otp": False,
            "user": user,
            "session_token": token,
            "expires_at": expires_at,
        }

    @classmethod
    async def verify_login_otp(
        cls,
        db: AsyncSession,
        redis: aioredis.Redis,
        otp_token: str,
        code: str,
        ip_address: Optional[str] = None,
        device_info: Optional[dict] = None,
    ) -> Tuple[User, str, datetime]:
        pending_key = f"login_pending:{otp_token}"
        user_id = await redis.get(pending_key)
        if not user_id:
            raise HTTPException(401, "This sign-in request expired. Start again.")

        user = (
            await db.execute(select(User).where(User.id == uuid.UUID(user_id)))
        ).scalar_one_or_none()
        if not user:
            raise HTTPException(401, "This sign-in request expired. Start again.")

        await cls._consume_otp(db, user, "login", code)
        await redis.delete(pending_key)
        token, expires_at = await cls.create_session(
            db, redis, user, ip_address, device_info, method="email_otp"
        )
        await db.commit()
        return user, token, expires_at


    @classmethod
    async def forgot_password(
        cls, db: AsyncSession, redis: aioredis.Redis, email: str
    ) -> None:
        user = (
            await db.execute(select(User).where(User.email == _normalise(email)))
        ).scalar_one_or_none()
        if not user or not user.is_active or not user.email:
            return

        token = uuid.uuid4().hex
        await redis.set(f"user_reset_token:{token}", str(user.id), ex=15 * 60)
        link = f"{settings.APP_URL}/reset-password?token={token}"
        await send_user_reset_password_email(user.email, user.first_name, link)

    @classmethod
    async def reset_password(
        cls, db: AsyncSession, redis: aioredis.Redis, token: str, new_password: str
    ) -> None:
        key = f"user_reset_token:{token}"
        user_id = await redis.get(key)
        if not user_id:
            raise HTTPException(400, "Invalid or expired reset link.")

        user = (
            await db.execute(select(User).where(User.id == uuid.UUID(user_id)))
        ).scalar_one_or_none()
        if not user:
            raise HTTPException(404, "Account not found.")

        user.password_hash = AdminAuthService.hash_password(new_password)
        user.email_verified_at = user.email_verified_at or datetime.now(timezone.utc)
        await cls.revoke_user_sessions(
            db, redis, user.id, revoke_api_keys=True
        )
        await redis.delete(key)
        await db.commit()


    @staticmethod
    async def _get_user(db: AsyncSession, user_id) -> User:
        user = (
            await db.execute(select(User).where(User.id == user_id))
        ).scalar_one_or_none()
        if not user:
            raise HTTPException(404, "Account not found.")
        return user

    @classmethod
    async def update_profile(
        cls, db: AsyncSession, user_id, payload: Any
    ) -> Tuple[User, bool]:
        """
        Apply a profile edit. Changing the email starts verification again,
        otherwise the account could not sign in afterwards.
        """
        user = await cls._get_user(db, user_id)

        first_name, last_name = (
            _split_name(payload.name) if payload.name else (user.first_name, user.last_name)
        )
        username = _normalise(payload.username) if payload.username else user.username
        email = _normalise(payload.email) if payload.email else user.email
        mobile = (
            re.sub(r"[\s-]+", "", payload.mobile) if payload.mobile else user.mobile
        )

        if payload.email and not EMAIL_RE.match(email):
            raise HTTPException(422, "Enter a valid email address.")

        if username and username != user.username:
            clash = (
                await db.execute(
                    select(User).where(User.username == username, User.id != user.id)
                )
            ).scalar_one_or_none()
            if clash:
                raise HTTPException(409, "That username is already taken.")

        email_changed = bool(payload.email) and email != user.email
        if email_changed:
            clash = (
                await db.execute(
                    select(User).where(User.email == email, User.id != user.id)
                )
            ).scalar_one_or_none()
            if clash:
                raise HTTPException(409, "An account with that email already exists.")

        if mobile and mobile != user.mobile:
            clash = (
                await db.execute(
                    select(User).where(User.mobile == mobile, User.id != user.id)
                )
            ).scalar_one_or_none()
            if clash:
                raise HTTPException(409, "An account with that mobile number already exists.")

        user.first_name = first_name
        user.last_name = last_name
        user.username = username
        user.mobile = mobile

        code = None
        if email_changed:
            user.email = email
            user.email_verified_at = None
            code = await cls.issue_otp(db, user, "verify_email")

        await db.commit()

        if code:
            await send_otp_email(email, user.first_name, code, "verify_email")
        return user, bool(code)

    @classmethod
    async def change_password(
        cls,
        db: AsyncSession,
        redis: aioredis.Redis,
        user_id,
        current_password: str,
        new_password: str,
    ) -> None:
        user = await cls._get_user(db, user_id)
        if not user.password_hash:
            raise HTTPException(
                400,
                "This account has no password yet. Use the forgot-password link to set one.",
            )
        if not AdminAuthService.verify_password(current_password, user.password_hash):
            raise HTTPException(400, "Your current password is incorrect.")

        user.password_hash = AdminAuthService.hash_password(new_password)
        await cls.revoke_user_sessions(db, redis, user.id)
        await db.commit()


    @classmethod
    async def create_user_by_admin(
        cls,
        db: AsyncSession,
        redis: aioredis.Redis,
        payload: Any,
    ) -> Tuple[User, bool]:
        username = _normalise(payload.username)
        email = _normalise(payload.email)
        mobile = re.sub(r"[\s-]+", "", payload.mobile)

        if not EMAIL_RE.match(email):
            raise HTTPException(422, "Enter a valid email address.")
        await cls._assert_available(db, username, email, mobile)

        first_name, last_name = _split_name(payload.name)
        setup_sent = not bool(payload.password)

        user = User(
            username=username,
            email=email,
            mobile=mobile,
            password_hash=(
                AdminAuthService.hash_password(payload.password)
                if payload.password
                else None
            ),
            auth_provider="admin",
            first_name=first_name,
            last_name=last_name,
            is_active=True,
            is_banned=False,
            email_verified_at=datetime.now(timezone.utc),
            telegram_id=None,
        )
        db.add(user)
        await db.flush()

        if setup_sent:
            token = uuid.uuid4().hex
            await redis.set(f"user_reset_token:{token}", str(user.id), ex=24 * 3600)
            link = f"{settings.APP_URL}/reset-password?token={token}"
            await db.commit()
            await send_account_created_email(
                email, first_name, username, link
            )
        else:
            await db.commit()

        return user, setup_sent
