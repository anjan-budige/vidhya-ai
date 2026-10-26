"""Vidhya Bot — API-key login helpers.

The bot no longer builds Telegram initData. A user connects once with
`/login <api-key>`; every backend request then uses that key.
"""

import logging
from typing import Optional

import httpx

from api_client import link_api_key
from session_store import UserSession, save_session

logger = logging.getLogger("vidhya.auth")


async def login_with_api_key(
    telegram_id: int, api_key: str
) -> Optional[UserSession]:
    try:
        data = await link_api_key(api_key, telegram_id)
    except httpx.HTTPStatusError as e:
        detail = "This API key is invalid or disabled."
        try:
            detail = e.response.json().get("detail", detail)
        except Exception:
            pass
        logger.warning("API key login failed for %s: %s", telegram_id, detail)
        raise ValueError(detail)

    sess = UserSession(
        telegram_id=telegram_id,
        api_key=api_key,
        user_id=data["user_id"],
        plan_name="free",
    )
    save_session(sess)
    return sess
