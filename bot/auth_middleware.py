"""
Vidhya Bot — Auth Middleware
Ensures every incoming message from a registered Telegram user
has a valid backend session. Auto-registers new users.
"""

import hashlib
import hmac
import logging
import time
import urllib.parse
from typing import Optional

import httpx

from api_client import telegram_login, activate_free_plan
from config import get_settings
from session_store import UserSession, get_session, save_session

settings = get_settings()
logger = logging.getLogger("vidhya.auth")


def build_init_data(user_id: int, first_name: str, username: Optional[str]) -> str:
    """
    Construct a Telegram-style initData string for bot-originated logins.
    In production WebApps, initData comes from the client.
    For bot (non-WebApp) users, we build a bot-verified payload.
    """
    auth_date = int(time.time())
    user_obj = {
        "id": user_id,
        "first_name": first_name,
        "username": username or "",
    }
    import json
    user_json = json.dumps(user_obj, separators=(",", ":"))

    params = {
        "auth_date": str(auth_date),
        "user": user_json,
    }

    # Build data-check-string per Telegram spec
    data_check_string = "\n".join(
        f"{k}={v}" for k, v in sorted(params.items())
    )

    # Sign with BOT_TOKEN
    secret_key = hmac.new(
        b"WebAppData",
        settings.TELEGRAM_BOT_TOKEN.encode(),
        hashlib.sha256
    ).digest()

    hash_val = hmac.new(
        secret_key,
        data_check_string.encode(),
        hashlib.sha256
    ).hexdigest()

    params["hash"] = hash_val
    return urllib.parse.urlencode(params)


async def ensure_session(
    telegram_id: int,
    first_name: str,
    username: Optional[str] = None,
    force_refresh: bool = False,
) -> Optional[UserSession]:
    """
    Returns a valid UserSession for the given Telegram user.
    If none exists (or force_refresh), calls the backend login endpoint.
    Auto-activates the free plan for brand-new users.
    """
    if not force_refresh:
        sess = get_session(telegram_id)
        if sess:
            return sess

    # Build initData and authenticate with backend
    try:
        init_data = build_init_data(telegram_id, first_name, username)
        data = await telegram_login(init_data)
    except httpx.HTTPStatusError as e:
        logger.error(f"Backend login failed for {telegram_id}: {e.response.text}")
        return None
    except Exception as e:
        logger.error(f"Login error for {telegram_id}: {e}")
        return None

    session_token = data["session_token"]
    is_new_user = data.get("is_new_user", False)

    # Auto-activate free plan for new users
    if is_new_user:
        try:
            await activate_free_plan(session_token)
            logger.info(f"Free plan activated for new user {telegram_id}")
        except Exception as e:
            logger.warning(f"Free plan activation failed for {telegram_id}: {e}")

    sess = UserSession(
        telegram_id=telegram_id,
        session_token=session_token,
        user_id=data["user_id"],
        plan_name=data.get("plan_name", "free"),
    )
    save_session(sess)
    return sess
