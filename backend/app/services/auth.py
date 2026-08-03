"""
╔══════════════════════════════════════════════════════════════════╗
║  VIDHYA BOT — Authentication Service                             ║
║  Provides: Telegram InitData HMAC validation, Admin password      ║
║  hashing (Argon2id), login lockout protection, and TOTP 2FA.     ║
╚══════════════════════════════════════════════════════════════════╝
"""

import hmac
import hashlib
import json
import urllib.parse
import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional, Tuple, Dict

import pyotp
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
import redis.asyncio as aioredis
from fastapi import HTTPException, status
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.user import User
from app.models.admin import Admin
from app.models.session import Session
from app.redis_client import RedisKeys
from app.schemas.auth import TelegramAuthData, LoginResponse, AdminLoginResponse

settings = get_settings()
ph = PasswordHasher()


def verify_telegram_webapp_signature(init_data: str, bot_token: str) -> dict:
    """
    Validate Telegram WebApp initData HMAC-SHA256 signature.
    Returns parsed user dictionary if valid, raises 401 Unauthorized otherwise.
    """
    try:
        # Parse query string
        params = dict(urllib.parse.parse_qsl(init_data, keep_blank_values=True))
        if "hash" not in params:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication failed: missing hash parameter."
            )
        
        tg_hash = params.pop("hash")
        
        # Sort keys alphabetically and format as key=value separated by \n
        sorted_params = sorted(params.items())
        data_check_string = "\n".join(f"{k}={v}" for k, v in sorted_params)
        
        # Calculate WebApp secret key from bot token
        secret_key = hmac.new(b"WebAppData", bot_token.encode("utf-8"), hashlib.sha256).digest()
        computed_hash = hmac.new(secret_key, data_check_string.encode("utf-8"), hashlib.sha256).hexdigest()
        
        # Signature validation
        if computed_hash != tg_hash:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication failed: invalid Telegram signature."
            )
        
        # Parse nested 'user' JSON object
        user_str = params.get("user")
        if not user_str:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication failed: missing user data in initData."
            )
            
        # Prevent Replay Attacks by checking auth_date
        auth_date = params.get("auth_date")
        if not auth_date:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication failed: missing auth_date."
            )
            
        # Telegram recommends max age of 24 hours (86400 seconds)
        import time
        if time.time() - int(auth_date) > 86400:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication failed: initData expired."
            )
            
        return json.loads(user_str)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Failed to parse Telegram auth data: {str(e)}"
        )


class TelegramAuthService:
    """Handles Telegram WebApp user authentication and session management."""

    @staticmethod
    async def authenticate_user(
        init_data: str,
        db: AsyncSession,
        redis: aioredis.Redis,
        ip_address: Optional[str] = None,
        device_info: Optional[dict] = None
    ) -> Tuple[User, str, datetime, bool]:
        """
        Authenticate Telegram user, provisioning account if new.
        Creates a session in Redis and Postgres.
        
        Returns:
            Tuple[User, session_token, expires_at, is_new_user]
        """
        # 1. Parse and verify data
        tg_user = verify_telegram_webapp_signature(init_data, settings.TELEGRAM_BOT_TOKEN)
        telegram_id = int(tg_user["id"])
        
        # 2. Check if user exists
        result = await db.execute(select(User).where(User.telegram_id == telegram_id))
        user = result.scalar_one_or_none()
        is_new_user = False
        
        if not user:
            # Provision new user
            is_new_user = True
            user = User(
                telegram_id=telegram_id,
                telegram_username=tg_user.get("username"),
                first_name=tg_user.get("first_name", "Telegram User"),
                last_name=tg_user.get("last_name"),
                photo_url=tg_user.get("photo_url"),
                language_code=tg_user.get("language_code", "en"),
                is_active=True,
                is_banned=False,
                last_login_at=datetime.now(timezone.utc)
            )
            db.add(user)
            await db.flush()  # Populates user.id
        else:
            # Update existing user profile if changed
            user.first_name = tg_user.get("first_name", user.first_name)
            user.last_name = tg_user.get("last_name", user.last_name)
            user.telegram_username = tg_user.get("username", user.telegram_username)
            user.photo_url = tg_user.get("photo_url", user.photo_url)
            user.last_login_at = datetime.now(timezone.utc)
        
        if user.is_banned:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Account is banned: {user.ban_reason or 'Contact support.'}"
            )
            
        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Account is deactivated."
            )
            
        # 3. Create Session Token and Expiry (30 days TTL)
        session_token = f"tgs_{uuid.uuid4().hex}"
        expires_at = datetime.now(timezone.utc) + timedelta(days=30)
        
        # 4. Save Session to Postgres
        session_db = Session(
            user_id=user.id,
            session_token=session_token,
            device_info=device_info,
            ip_address=ip_address,
            expires_at=expires_at,
            is_active=True
        )
        db.add(session_db)
        
        # 5. Save Session to Redis (Fast Access)
        session_key = RedisKeys.session(session_token)
        await redis.hset(
            session_key,
            mapping={
                "user_id": str(user.id),
                "telegram_id": str(user.telegram_id),
                "username": user.telegram_username or ""
            }
        )
        await redis.expire(session_key, 30 * 24 * 3600)  # 30 days in seconds
        
        return user, session_token, expires_at, is_new_user


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
        # 1. Lockout Check
        lockout_key = RedisKeys.rate_limit_login(ip_address)
        failed_attempts = await redis.get(lockout_key)
        if failed_attempts and int(failed_attempts) >= 5:
            raise HTTPException(
                status_code=status.HTTP_423_LOCKED,
                detail="Too many failed login attempts. Try again in 15 minutes."
            )
            
        # 2. Query Admin
        result = await db.execute(select(Admin).where(Admin.username == username))
        admin = result.scalar_one_or_none()
        
        # Lockout check on DB side
        if admin and admin.is_locked:
            raise HTTPException(
                status_code=status.HTTP_423_LOCKED,
                detail="Account is temporarily locked. Contact a superadmin."
            )
            
        # 3. Verify Password
        if not admin or not cls.verify_password(password, admin.password_hash):
            # Increment lockout counter in Redis (15 mins TTL)
            current_failed = await redis.incr(lockout_key)
            if current_failed == 1:
                await redis.expire(lockout_key, 15 * 60)
                
            # If failed attempts >= 5, lock admin account in DB
            if admin and current_failed >= 5:
                admin.locked_until = datetime.now(timezone.utc) + timedelta(minutes=15)
                admin.failed_login_count = admin.failed_login_count + 1
                await db.commit()
                
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid username or password."
            )
            
        # Reset failed attempts on success
        await redis.delete(lockout_key)
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
            
        # Verify passcode
        totp = pyotp.TOTP(admin.totp_secret)
        if not totp.verify(totp_code, valid_window=2):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid verification code."
            )
            
        # Promote session to fully active (24 hours TTL)
        new_token = f"ads_{uuid.uuid4().hex}"
        expires_at = datetime.now(timezone.utc) + timedelta(hours=24)
        
        # Delete pre-auth session
        await redis.delete(session_key)
        
        # Write active session
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
            
        # Generate pyotp secret and provisioning URI
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
            # We silently fail to prevent email enumeration attacks
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
        
        await redis.delete(reset_key)
        return True

    @classmethod
    async def update_password(
        cls,
        admin_id: uuid.UUID,
        current_password: str,
        new_password: str,
        db: AsyncSession
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
        return True

