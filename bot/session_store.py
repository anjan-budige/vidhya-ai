"""
Vidhya Bot — in-process session storage.

Maps a Telegram id to the API key used for backend requests and the
session (conversation) currently selected in the chat.
"""

import logging
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger("vidhya.session")


@dataclass
class UserSession:
    telegram_id: int
    api_key: str
    user_id: str
    plan_name: str = "free"
    current_session_id: Optional[str] = None
    pending_message: Optional[str] = None
    pending_at: Optional[float] = None
    skip_idle_once: bool = False


# telegram_id → UserSession
_sessions: dict[int, UserSession] = {}


def get_session(telegram_id: int) -> Optional[UserSession]:
    return _sessions.get(telegram_id)


def save_session(session: UserSession) -> None:
    _sessions[session.telegram_id] = session


def delete_session(telegram_id: int) -> None:
    _sessions.pop(telegram_id, None)


def set_current_session(telegram_id: int, session_id: Optional[str]) -> None:
    sess = _sessions.get(telegram_id)
    if sess:
        sess.current_session_id = session_id
        sess.skip_idle_once = True


def clear_pending(telegram_id: int) -> Optional[str]:
    sess = _sessions.get(telegram_id)
    if not sess:
        return None
    message = sess.pending_message
    sess.pending_message = None
    sess.pending_at = None
    return message


def update_plan(telegram_id: int, plan_name: str) -> None:
    sess = _sessions.get(telegram_id)
    if sess:
        sess.plan_name = plan_name
