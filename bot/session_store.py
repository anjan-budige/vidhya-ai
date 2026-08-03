"""
Vidhya Bot — Session Middleware & Storage
Maps Telegram user_id ↔ backend session_token + active conversation_id.
Uses in-memory dict (sufficient for single-instance bot).
"""

import logging
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger("vidhya.session")


@dataclass
class UserSession:
    telegram_id: int
    session_token: str
    user_id: str
    plan_name: str = "free"
    active_conv_id: Optional[str] = None


# In-process session store: telegram_id → UserSession
_sessions: dict[int, UserSession] = {}


def get_session(telegram_id: int) -> Optional[UserSession]:
    return _sessions.get(telegram_id)


def save_session(session: UserSession) -> None:
    _sessions[session.telegram_id] = session


def delete_session(telegram_id: int) -> None:
    _sessions.pop(telegram_id, None)


def set_active_conversation(telegram_id: int, conv_id: Optional[str]) -> None:
    sess = _sessions.get(telegram_id)
    if sess:
        sess.active_conv_id = conv_id


def update_plan(telegram_id: int, plan_name: str) -> None:
    sess = _sessions.get(telegram_id)
    if sess:
        sess.plan_name = plan_name
