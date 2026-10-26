"""Vidhya Bot — User API key service"""

import hashlib
import json
import secrets
from datetime import datetime, timezone
from typing import Optional, Tuple

import redis.asyncio as aioredis
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.models.user_api_key import UserApiKey
from app.schemas.auth import CurrentUser


class ApiKeyService:
    PREFIX = "vdk_"

    @staticmethod
    def hash_key(raw: str) -> str:
        return hashlib.sha256(raw.strip().encode("utf-8")).hexdigest()

    @staticmethod
    async def get_active_key(
        db: AsyncSession, user_id
    ) -> Optional[UserApiKey]:
        result = await db.execute(
            select(UserApiKey)
            .where(
                UserApiKey.user_id == user_id,
                UserApiKey.revoked_at.is_(None),
            )
            .order_by(UserApiKey.created_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    @classmethod
    async def generate(
        cls,
        db: AsyncSession,
        user_id,
        created_by=None,
        label: str = "default",
        enabled: bool = False,
    ) -> Tuple[str, UserApiKey]:
        raw = cls.PREFIX + secrets.token_urlsafe(32)
        row = UserApiKey(
            user_id=user_id,
            label=label or "default",
            key_prefix=raw[:12],
            key_hash=cls.hash_key(raw),
            is_enabled=enabled,
            created_by=created_by,
        )
        db.add(row)
        await db.flush()
        return raw, row

    @classmethod
    async def clear_bot_binding(
        cls, db: AsyncSession, redis: aioredis.Redis, user_id
    ) -> None:
        """A revoked/rotated key must not keep a Telegram chat logged in."""
        user = (
            await db.execute(select(User).where(User.id == user_id))
        ).scalar_one_or_none()
        if not user or not user.telegram_id:
            return
        await redis.delete(
            f"bot:session:{user.telegram_id}",
            f"bot:binding:{user.id}",
        )
        user.telegram_id = None

    @classmethod
    async def rotate(
        cls,
        db: AsyncSession,
        user_id,
        created_by=None,
        label: Optional[str] = None,
        redis: Optional[aioredis.Redis] = None,
    ) -> Tuple[str, UserApiKey]:
        existing = await cls.get_active_key(db, user_id)
        enabled = existing.is_enabled if existing else True
        keep_label = label or (existing.label if existing else "default")

        rows = (
            await db.execute(
                select(UserApiKey).where(UserApiKey.user_id == user_id)
            )
        ).scalars().all()

        if redis is not None:
            await cls.clear_bot_binding(db, redis, user_id)
            for row in rows:
                await redis.delete(f"apikey:{row.key_hash}")

        # The previous key is deleted, not archived: only the current key exists.
        for row in rows:
            await db.delete(row)
        await db.flush()

        return await cls.generate(
            db,
            user_id,
            created_by=created_by,
            label=keep_label,
            enabled=enabled,
        )

    @classmethod
    async def set_enabled(
        cls,
        db: AsyncSession,
        user_id,
        enabled: bool,
        redis: Optional[aioredis.Redis] = None,
    ) -> UserApiKey:
        row = await cls.get_active_key(db, user_id)
        if not row:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No API key exists for this user.",
            )
        row.is_enabled = enabled
        if redis is not None:
            await redis.delete(f"apikey:{row.key_hash}")
        return row

    @classmethod
    async def revoke(
        cls,
        db: AsyncSession,
        user_id,
        redis: Optional[aioredis.Redis] = None,
    ) -> int:
        rows = (
            await db.execute(
                select(UserApiKey).where(UserApiKey.user_id == user_id)
            )
        ).scalars().all()

        if redis is not None:
            await cls.clear_bot_binding(db, redis, user_id)
            for row in rows:
                await redis.delete(f"apikey:{row.key_hash}")

        for row in rows:
            await db.delete(row)
        await db.flush()
        return len(rows)

    @classmethod
    async def authenticate(
        cls,
        db: AsyncSession,
        redis: aioredis.Redis,
        raw_key: str,
    ) -> CurrentUser:
        raw_key = (raw_key or "").strip()
        if not raw_key.startswith(cls.PREFIX):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid API key.",
            )

        key_hash = cls.hash_key(raw_key)

        # Redis is the hot auth path; Postgres is only hit on a cache miss.
        cached = await redis.get(f"apikey:{key_hash}")
        if cached:
            try:
                cached_user = json.loads(cached)
            except Exception:
                cached_user = None
            if cached_user:
                if cached_user.get("is_banned"):
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="Account banned.",
                    )
                if not cached_user.get("is_active"):
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="Account is deactivated.",
                    )
                return CurrentUser(**cached_user)

        result = await db.execute(
            select(UserApiKey).where(
                UserApiKey.key_hash == key_hash,
                UserApiKey.revoked_at.is_(None),
            )
        )
        key = result.scalar_one_or_none()
        if not key:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or revoked API key.",
            )
        if not key.is_enabled:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="API access is disabled. Enable it in your account settings.",
            )

        user = (
            await db.execute(select(User).where(User.id == key.user_id))
        ).scalar_one_or_none()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found.",
            )
        if user.is_banned:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Account banned: {user.ban_reason or 'Contact support.'}",
            )
        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Account is deactivated.",
            )

        marker = f"apikey:seen:{key.id}"
        if not await redis.get(marker):
            key.last_used_at = datetime.now(timezone.utc)
            await redis.set(marker, "1", ex=60)

        current = CurrentUser(
            id=user.id,
            telegram_id=user.telegram_id,
            username=user.username,
            email=user.email,
            mobile=user.mobile,
            first_name=user.first_name,
            last_name=user.last_name,
            telegram_username=user.telegram_username,
            auth_provider=user.auth_provider,
            email_verified_at=user.email_verified_at,
            is_active=user.is_active,
            is_banned=user.is_banned,
        )
        await redis.set(
            f"apikey:{key_hash}",
            json.dumps(current.model_dump(mode="json")),
            ex=60,
        )
        return current
