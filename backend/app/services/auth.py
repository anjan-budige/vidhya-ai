import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional, Tuple

import pyotp
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
import redis.asyncio as aioredis
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.admin import Admin
from app.redis_client import RedisKeys
from app.schemas.auth import AdminLoginResponse

settings = get_settings()
ph = PasswordHasher()


class AdminAuthService:
    """Handles admin panel authentication, Argon2id, lockout, and TOTP 2FA."""

    @staticmethod
    def hash_password(password: str) -> str:
        """Hash password using Argon2id."""
        return ph.hash(password)

    @staticmethod
    def verify_password(password: str, hashed_password: str) -> bool:
        """Verify password against Argon2id hash."""
        try:
            return ph.verify(hashed_password, password)
        except VerifyMismatchError:
            return False

    @classmethod
    async def authenticate_admin(
        cls,
        username: str,
        password: str,
        db: AsyncSession,
        redis: aioredis.Redis,
        ip_address: str
    ) -> Tuple[Admin, str, bool, datetime]:
        """
        Authenticate admin using username and password.
        Enforces login lockout and manages 2FA flow.
        
        Returns:
            Tuple[Admin, session_token, requires_totp, expires_at]
        """
        # 1. Lockout Check — both the source IP and the targeted account are
        # tracked so rotating proxy addresses cannot reset the counter.
        lockout_key = RedisKeys.rate_limit_login(ip_address)
        account_key = RedisKeys.rate_limit_admin_login(username)
        failed_attempts = await redis.get(lockout_key)
        account_attempts = await redis.get(account_key)
        if (failed_attempts and int(failed_attempts) >= 5) or (
            account_attempts and int(account_attempts) >= 5
        ):
            raise HTTPException(
                status_code=status.HTTP_423_LOCKED,
                detail="Too many failed login attempts. Try again in 15 minutes."
            )
            
        # 2. Query Admin
        result = await db.execute(select(Admin).where(Admin.username == username))
        admin = result.scalar_one_or_none()
        
        if admin and admin.is_locked:
            raise HTTPException(
                status_code=status.HTTP_423_LOCKED,
                detail="Account is temporarily locked. Contact a superadmin."
            )
            
        # 3. Verify Password
        if not admin or not cls.verify_password(password, admin.password_hash):
            current_failed = await redis.incr(lockout_key)
            if current_failed == 1:
                await redis.expire(lockout_key, 15 * 60)
            account_failed = await redis.incr(account_key)
            if account_failed == 1:
                await redis.expire(account_key, 15 * 60)
                
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid username or password."
            )
            
        await redis.delete(lockout_key, account_key)
        if admin.failed_login_count > 0 or admin.locked_until:
            admin.failed_login_count = 0
            admin.locked_until = None
            
        if not admin.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Admin account is deactivated."
            )
            
        # 4. Check if 2FA (TOTP) is required
        requires_totp = admin.totp_enabled and bool(admin.totp_secret)
        
        # 5. Provision Session Token
        # If TOTP is required, this is a pre-auth session. If not, it is a fully active session.
        session_token = f"ads_{uuid.uuid4().hex}"
        expires_at = datetime.now(timezone.utc) + (timedelta(minutes=10) if requires_totp else timedelta(hours=24))
        
        session_key = RedisKeys.admin_session(session_token)
        await redis.hset(
            session_key,
            mapping={
                "admin_id": str(admin.id),
                "username": admin.username,
                "role": admin.role,
                "is_pre_auth": "true" if requires_totp else "false"
            }
        )
        await redis.expire(session_key, 600 if requires_totp else 24 * 3600)
        
        admin.last_login_at = datetime.now(timezone.utc)
        
        return admin, session_token, requires_totp, expires_at

    @staticmethod
    async def verify_totp(
        session_token: str,
        totp_code: str,
        db: AsyncSession,
        redis: aioredis.Redis
    ) -> Tuple[Admin, str, datetime]:
        """
        Verify TOTP passcode using the pre-auth session token.
        Promotes the session to fully active on success.
        """
        session_key = RedisKeys.admin_session(session_token)
        session_data = await redis.hgetall(session_key)
        
        if not session_data or session_data.get("is_pre_auth") != "true":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired session. Please log in again."
            )
            
        admin_id = uuid.UUID(session_data["admin_id"])
        result = await db.execute(select(Admin).where(Admin.id == admin_id))
        admin = result.scalar_one_or_none()
        
        if not admin or not admin.is_active or admin.is_locked:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Admin account is inactive or locked."
            )
            
        # Limit guesses against this pre-auth session. A six-digit code must
        # not remain brute-forceable for the full ten-minute session lifetime.
        attempts = int(session_data.get("totp_attempts", "0") or "0")
        if attempts >= 5:
            await redis.delete(session_key)
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many verification attempts. Sign in again.",
            )

        totp = pyotp.TOTP(admin.totp_secret)
        if not totp.verify(totp_code, valid_window=2):
            attempts = await redis.hincrby(session_key, "totp_attempts", 1)
            if attempts >= 5:
                await redis.delete(session_key)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid verification code."
            )
            
        new_token = f"ads_{uuid.uuid4().hex}"
        expires_at = datetime.now(timezone.utc) + timedelta(hours=24)
        
        await redis.delete(session_key)
        
        new_session_key = RedisKeys.admin_session(new_token)
        await redis.hset(
            new_session_key,
            mapping={
                "admin_id": str(admin.id),
                "username": admin.username,
                "role": admin.role,
                "is_pre_auth": "false"
            }
        )
        await redis.expire(new_session_key, 24 * 3600)
        
        return admin, new_token, expires_at

    @staticmethod
    async def provision_totp(
        admin_id: uuid.UUID,
        db: AsyncSession
    ) -> Tuple[str, str]:
        """
        Provision a new TOTP secret for an admin.
        Returns the raw secret and the provisioning URI.
        Note: does not enable TOTP until validated.
        """
        result = await db.execute(select(Admin).where(Admin.id == admin_id))
        admin = result.scalar_one_or_none()
        if not admin:
            raise HTTPException(status_code=404, detail="Admin not found.")
        if admin.totp_enabled:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    "Two-factor authentication is already enabled. "
                    "Ask a superadmin to disable it before re-enrolling."
                ),
            )
            
        secret = pyotp.random_base32()
        totp = pyotp.TOTP(secret)
        provisioning_uri = totp.provisioning_uri(
            name=admin.username,
            issuer_name=settings.APP_NAME
        )
        
        # Save temp secret in DB, to be validated next
        admin.totp_secret = secret
        admin.totp_enabled = False  # Stay disabled until verified
        
        return secret, provisioning_uri

    @staticmethod
    async def confirm_totp(
        admin_id: uuid.UUID,
        code: str,
        db: AsyncSession
    ) -> bool:
        """
        Validate and enable TOTP for the admin.
        """
        result = await db.execute(select(Admin).where(Admin.id == admin_id))
        admin = result.scalar_one_or_none()
        if not admin or not admin.totp_secret:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="TOTP has not been provisioned for this admin."
            )
            
        totp = pyotp.TOTP(admin.totp_secret)
        if totp.verify(code, valid_window=2):
            admin.totp_enabled = True
            return True
            
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid code verification. Setup failed."
        )

    @staticmethod
    async def disable_totp(
        admin_id: uuid.UUID,
        db: AsyncSession
    ) -> bool:
        """
        Disable TOTP for the admin.
        """
        result = await db.execute(select(Admin).where(Admin.id == admin_id))
        admin = result.scalar_one_or_none()
        if not admin:
            raise HTTPException(status_code=404, detail="Admin not found.")
            
        admin.totp_secret = None
        admin.totp_enabled = False
        return True

    @staticmethod
    async def revoke_all_sessions(admin_id: uuid.UUID, redis: aioredis.Redis) -> None:
        admin_id_str = str(admin_id)
        async for key in redis.scan_iter(match="admin_session:*", count=200):
            if await redis.hget(key, "admin_id") == admin_id_str:
                await redis.delete(key)

    @classmethod
    async def generate_password_reset_token(
        cls,
        email: str,
        db: AsyncSession,
        redis: aioredis.Redis
    ) -> str:
        """
        Generates a secure password reset token and saves it to Redis.
        Returns the token.
        """
        result = await db.execute(select(Admin).where(Admin.email == email))
        admin = result.scalar_one_or_none()
        if not admin or not admin.is_active:
            return None
            
        token = uuid.uuid4().hex
        reset_key = f"admin_reset_token:{token}"
        await redis.set(reset_key, str(admin.id), ex=15 * 60) # 15 minutes TTL
        return token

    @classmethod
    async def reset_password(
        cls,
        token: str,
        new_password: str,
        db: AsyncSession,
        redis: aioredis.Redis
    ) -> bool:
        """
        Validates token and resets password, also disabling 2FA.
        """
        reset_key = f"admin_reset_token:{token}"
        admin_id_str = await redis.get(reset_key)
        
        if not admin_id_str:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid or expired reset token."
            )
            
        admin_id = uuid.UUID(admin_id_str)
        result = await db.execute(select(Admin).where(Admin.id == admin_id))
        admin = result.scalar_one_or_none()
        
        if not admin:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Admin not found."
            )
            
        admin.password_hash = cls.hash_password(new_password)
        admin.totp_secret = None
        admin.totp_enabled = False
        admin.failed_login_count = 0
        admin.locked_until = None

        await cls.revoke_all_sessions(admin.id, redis)
        await redis.delete(reset_key)
        return True

    @classmethod
    async def update_password(
        cls,
        admin_id: uuid.UUID,
        current_password: str,
        new_password: str,
        db: AsyncSession,
        redis: aioredis.Redis,
    ) -> bool:
        """
        Updates the password for an authenticated admin after verifying current password.
        """
        result = await db.execute(select(Admin).where(Admin.id == admin_id))
        admin = result.scalar_one_or_none()
        
        if not admin:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Admin not found."
            )
            
        if not cls.verify_password(current_password, admin.password_hash):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect current password."
            )
            
        admin.password_hash = cls.hash_password(new_password)
        await cls.revoke_all_sessions(admin.id, redis)
        return True

