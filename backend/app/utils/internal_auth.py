"""Server-to-server credential used only by the Telegram bot bridge."""

import hashlib
import hmac
from collections.abc import Mapping

from app.config import get_settings

_CONTEXT = b"vidhya:internal:telegram-bot:v1"
_HEADER = "X-Bot-Token"


def bot_service_token() -> str:
    secret = get_settings().SECRET_KEY.encode("utf-8")
    return hmac.new(secret, _CONTEXT, hashlib.sha256).hexdigest()


def is_telegram_bot_request(headers: Mapping[str, str]) -> bool:
    supplied = headers.get(_HEADER) or headers.get(_HEADER.lower()) or ""
    return bool(supplied) and hmac.compare_digest(supplied, bot_service_token())
