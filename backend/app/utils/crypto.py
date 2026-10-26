"""Symmetric encryption for provider credentials stored in the database."""

import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken

from app.config import get_settings


def _fernet_for(secret: str) -> Fernet:
    digest = hashlib.sha256(secret.encode("utf-8")).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def _fernet() -> Fernet:
    settings = get_settings()
    secret = settings.SETTINGS_ENCRYPTION_KEY or settings.SECRET_KEY
    return _fernet_for(secret)


def _payments_fernet() -> Fernet:
    settings = get_settings()
    if not settings.PAYMENTS_ENCRYPTION_KEY:
        raise RuntimeError(
            "PAYMENTS_ENCRYPTION_KEY is not set. Add it to the environment "
            "before saving payment gateway credentials."
        )
    digest = hashlib.sha256(settings.PAYMENTS_ENCRYPTION_KEY.encode("utf-8")).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def encrypt_secret(value: str) -> str:
    return _fernet().encrypt(value.encode("utf-8")).decode("utf-8")


def decrypt_secret(value: str) -> str:
    try:
        return _fernet().decrypt(value.encode("utf-8")).decode("utf-8")
    except InvalidToken:
        # Providers saved before SETTINGS_ENCRYPTION_KEY was set were encrypted
        # with SECRET_KEY. Read them so admins can re-save at their convenience.
        settings = get_settings()
        if not settings.SECRET_KEY:
            raise
        legacy = _fernet_for(settings.SECRET_KEY)
        return legacy.decrypt(value.encode("utf-8")).decode("utf-8")


def encrypt_payment_secret(value: str) -> str:
    return _payments_fernet().encrypt(value.encode("utf-8")).decode("utf-8")


def decrypt_payment_secret(value: str) -> str:
    return _payments_fernet().decrypt(value.encode("utf-8")).decode("utf-8")


def mask_secret(value: str) -> str:
    if not value:
        return ""
    return f"****{value[-4:]}" if len(value) > 4 else "****"
