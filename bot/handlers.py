"""Vidhya Bot — Telegram handlers.

Login is by API key (`/login <api-key>`). Sessions are saved chats with a
single `max_sessions` cap; there is no active/closed state.
"""

import logging
import time
from datetime import datetime, timezone
from typing import Optional

def _fmt_limit(value) -> str:
    return "∞" if value == -1 else str(value)


import httpx
from aiogram import Router, F, Bot
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, CallbackQuery
from aiogram.utils.chat_action import ChatActionSender

from api_client import (
    create_conversation,
    delete_conversation,
    get_ai_quota,
    get_conversation,
    get_my_subscription,
    get_platform_config,
    list_conversations,
    stream_ai_response,
)
from math_format import clean_math
from auth_middleware import login_with_api_key
from config import get_settings
from session_store import (
    UserSession,
    clear_pending,
    delete_session,
    get_session,
    save_session,
    set_current_session,
)
import keyboards as kb

logger = logging.getLogger("vidhya.handlers")
settings = get_settings()
router = Router()

MENU_ASK = "💬 Ask AI"
MENU_NEW = "🆕 New Chat"
MENU_SESSIONS = "📋 My Sessions"
MENU_DELETE = "🗑️ Delete Session"
MENU_USAGE = "⚡ Usage"
MENU_PLAN = "📊 My Plan"
MENU_HELP = "❓ Help"

MENU_TEXTS = {
    MENU_ASK,
    MENU_NEW,
    MENU_SESSIONS,
    MENU_DELETE,
    MENU_USAGE,
    MENU_PLAN,
    MENU_HELP,
}



def _now() -> datetime:
    return datetime.now(timezone.utc)


async def _config() -> dict:
    try:
        return await get_platform_config()
    except Exception:
        return {}


def _bot_cfg(cfg: dict) -> dict:
    return cfg.get("bot", {}) or {}


def _welcome_text(cfg: dict) -> str:
    bot = _bot_cfg(cfg)
    lines = [
        f"*{bot.get('welcome_title', 'Welcome to Vidhya AI')}*",
        (bot.get("welcome_message") or "").strip(),
        (bot.get("login_hint") or "Use /login <api-key> to connect your account.").strip(),
    ]

    if cfg.get("registration_enabled") and bot.get("show_register_link", True):
        url = cfg.get("register_url") or f"{settings.APP_URL}/register"
        register_hint = (bot.get("register_hint") or "").replace("{register_url}", url)
        if register_hint:
            lines.append(register_hint)

    return "\n\n".join(line for line in lines if line)


async def _send_welcome(message: Message) -> None:
    text = _welcome_text(await _config())
    try:
        await message.answer(text, parse_mode="Markdown")
    except Exception:
        await message.answer(text)


async def _get_session_or_welcome(message: Message) -> Optional[UserSession]:
    sess = get_session(message.from_user.id)
    if not sess:
        await _send_welcome(message)
    return sess


async def _create_session(sess: UserSession):
    try:
        return await create_conversation(sess.api_key), None, 200
    except httpx.HTTPStatusError as e:
        detail = "Could not create a session."
        try:
            detail = e.response.json().get("detail", detail)
        except Exception:
            pass
        return None, detail, e.response.status_code
    except Exception as e:
        logger.error("Create session failed: %s", e)
        return None, "Could not create a session.", 500


def _is_auth_failure(status: int, detail: str) -> bool:
    return status in (401, 403) and "Session limit" not in detail


async def _send_limit_hint(message, sess: UserSession, cfg: dict) -> None:
    text = _bot_cfg(cfg).get(
        "session_limit_text",
        "You have reached your session limit. Delete an existing chat to start a new one.",
    )
    try:
        conversations = await list_conversations(sess.api_key)
    except Exception:
        conversations = []

    if conversations:
        await message.answer(text, reply_markup=kb.delete_sessions_keyboard(conversations))
    else:
        await message.answer(text)


async def _send_to_session(message, bot: Bot, sess: UserSession, text: str) -> None:
    cfg = await _config()
    bot_cfg = _bot_cfg(cfg)

    reply = await message.answer("⏳ Thinking…")
    full = ""
    last_edit = 0.0

    async with ChatActionSender.typing(bot=bot, chat_id=message.chat.id):
        async for event in stream_ai_response(
            sess.api_key, text, sess.current_session_id
        ):
            if event["type"] == "token":
                full += event["text"]
                now = time.time()
                if now - last_edit > 1.0:
                    try:
                        await reply.edit_text(clean_math(full)[:3800] + " ⏳")
                    except Exception:
                        pass
                    last_edit = now

            elif event["type"] == "metadata" and event.get("conversation_id"):
                sess.current_session_id = event["conversation_id"]
                save_session(sess)

            elif event["type"] == "error":
                if event.get("status") in (401, 403) or event.get("code") == "auth":
                    delete_session(message.from_user.id)
                    await reply.edit_text(
                        "⚠️ Your API access is no longer valid. Use /login with a new key."
                    )
                else:
                    await reply.edit_text(f"⚠️ {event.get('detail', 'AI error.')}")
                return

            elif event["type"] == "done":
                break

    if not full.strip():
        await reply.edit_text("⚠️ No response from the AI.")
        return

    final_text = clean_math(full)[:4096]
    try:
        await reply.edit_text(final_text, parse_mode="Markdown")
    except Exception:
        try:
            await reply.edit_text(final_text)
        except Exception:
            await message.answer(final_text)



@router.message(CommandStart())
async def cmd_start(message: Message):
    sess = get_session(message.from_user.id)
    cfg = await _config()
    bot_cfg = _bot_cfg(cfg)

    if not sess:
        await _send_welcome(message)
        return

    text = (
        f"*{bot_cfg.get('welcome_title', 'Welcome to Vidhya AI')}*\n\n"
        f"Connected as *{message.from_user.first_name}*. "
        "Send a question or pick an option below."
    )
    await message.answer(text, reply_markup=kb.main_menu_keyboard(), parse_mode="Markdown")


@router.message(Command("login"))
async def cmd_login(message: Message):
    parts = (message.text or "").split(maxsplit=1)
    if len(parts) < 2 or not parts[1].strip():
        await message.answer(
            "Usage: `/login <api-key>`\n\n"
            "Create and enable a key in your web account, then paste it here.",
            parse_mode="Markdown",
        )
        return

    api_key = parts[1].strip()
    try:
        await login_with_api_key(message.from_user.id, api_key)
    except ValueError as e:
        await message.answer(f"⚠️ {e}")
        return

    try:
        await message.delete()
    except Exception:
        pass

    await message.answer(
        f"✅ Connected as *{message.from_user.first_name}*. Send a message to start.",
        reply_markup=kb.main_menu_keyboard(),
        parse_mode="Markdown",
    )


@router.message(Command("logout"))
async def cmd_logout(message: Message):
    delete_session(message.from_user.id)
    cfg = await _config()
    await message.answer(_welcome_text(cfg))


@router.message(F.text == MENU_HELP)
@router.message(Command("help"))
async def cmd_help(message: Message):
    await message.answer(
        "📚 *Vidhya AI commands*\n\n"
        "💬 Ask AI — send a question\n"
        "🆕 New Chat — start a new session\n"
        "📋 My Sessions — switch between saved chats\n"
        "🗑️ Delete Session — remove a chat\n"
        "⚡ Usage — messages and session usage\n"
        "📊 My Plan — your current plan\n"
        "🔑 /login <api-key> — connect your account\n"
        "🚪 /logout — disconnect this chat\n\n"
        f"🌐 Web app — chats, plans and account: {settings.APP_URL}",
        parse_mode="Markdown",
        reply_markup=kb.main_menu_keyboard(),
    )



@router.message(F.text == MENU_NEW)
@router.message(Command("newchat"))
async def cmd_new_session(message: Message):
    sess = await _get_session_or_welcome(message)
    if not sess:
        return

    data, error, status = await _create_session(sess)
    if error:
        if _is_auth_failure(status, error):
            delete_session(message.from_user.id)
            await _send_welcome(message)
            return
        await _send_limit_hint(message, sess, await _config())
        return

    sess.current_session_id = data["id"]
    sess.pending_message = None
    sess.pending_at = None
    sess.skip_idle_once = True
    save_session(sess)

    cfg = await _config()
    await message.answer(
        _bot_cfg(cfg).get("session_started_text", "New session started."),
        reply_markup=kb.main_menu_keyboard(),
    )


@router.message(F.text == MENU_SESSIONS)
@router.message(Command("chats"))
async def cmd_sessions(message: Message):
    sess = await _get_session_or_welcome(message)
    if not sess:
        return

    try:
        conversations = await list_conversations(sess.api_key)
    except Exception as e:
        logger.error("List sessions failed: %s", e)
        await message.answer("⚠️ Could not load your sessions.")
        return

    if not conversations:
        await message.answer("You have no saved sessions yet. Send a message to start one.")
        return

    await message.answer(
        "📋 *Your sessions*\nSelect one to continue.",
        parse_mode="Markdown",
        reply_markup=kb.sessions_keyboard(conversations),
    )


@router.message(F.text == MENU_DELETE)
@router.message(Command("deletechat"))
async def cmd_delete_sessions(message: Message):
    sess = await _get_session_or_welcome(message)
    if not sess:
        return

    try:
        conversations = await list_conversations(sess.api_key)
    except Exception:
        await message.answer("⚠️ Could not load your sessions.")
        return

    if not conversations:
        await message.answer("You have no sessions to delete.")
        return

    await message.answer(
        "🗑️ *Delete a session*\nThis removes the chat and its messages.",
        parse_mode="Markdown",
        reply_markup=kb.delete_sessions_keyboard(conversations),
    )



@router.message(F.text == MENU_USAGE)
@router.message(Command("usage"))
async def cmd_usage(message: Message):
    sess = await _get_session_or_welcome(message)
    if not sess:
        return

    try:
        quota = await get_ai_quota(sess.api_key)
    except Exception:
        await message.answer("⚠️ Could not load your usage.")
        return

    await message.answer(
        "⚡ *Your usage*\n\n"
        f"Daily messages: {quota.get('daily_messages_used', 0)} / "
        f"{_fmt_limit(quota.get('daily_messages_limit', 0))}\n"
        f"Monthly messages: {quota.get('monthly_messages_used', 0)} / "
        f"{_fmt_limit(quota.get('monthly_messages_limit', 0))}\n"
        f"Sessions: {quota.get('sessions_used', 0)} / {_fmt_limit(quota.get('max_sessions', 0))}\n"
        f"Plan: {quota.get('plan_name', 'free').capitalize()}",
        parse_mode="Markdown",
        reply_markup=kb.main_menu_keyboard(),
    )


@router.message(F.text == MENU_PLAN)
@router.message(Command("plan"))
async def cmd_plan(message: Message):
    sess = await _get_session_or_welcome(message)
    if not sess:
        return

    try:
        sub = await get_my_subscription(sess.api_key)
    except Exception:
        await message.answer("⚠️ Could not load your plan.")
        return

    cfg = await _config()
    plan_name = sub.get("plan_display_name") or "Free"
    lines = [
        "📊 *Your plan*",
        "",
        f"Plan: *{plan_name}*",
        f"Sessions: {sub.get('sessions_used', 0)} / {_fmt_limit(sub.get('max_sessions', 0))}",
        f"Daily messages: {sub.get('daily_messages_used', 0)} / {_fmt_limit(sub.get('daily_messages_limit', 0))}",
        f"Monthly messages: {sub.get('monthly_messages_used', 0)} / {_fmt_limit(sub.get('monthly_messages_limit', 0))}",
    ]
    if cfg.get("billing_enabled", True):
        lines.append("")
        lines.append(f"Browse plans and upgrade: {settings.APP_URL}/plans")
    else:
        lines.append("")
        lines.append("Open access — every feature is included.")

    await message.answer(
        "\n".join(lines), parse_mode="Markdown", reply_markup=kb.main_menu_keyboard()
    )


@router.message(F.text == MENU_ASK)
async def cmd_ask(message: Message):
    if not get_session(message.from_user.id):
        await _send_welcome(message)
        return
    await message.answer("Type your question below ⬇️", reply_markup=kb.main_menu_keyboard())



@router.callback_query(F.data == "cancel")
async def cb_cancel(callback: CallbackQuery):
    try:
        await callback.message.delete()
    except Exception:
        pass
    await callback.answer()


@router.callback_query(F.data == "continue_session")
async def cb_continue(callback: CallbackQuery, bot: Bot):
    sess = get_session(callback.from_user.id)
    if not sess:
        await callback.answer("Please /login first.", show_alert=True)
        return

    pending = clear_pending(callback.from_user.id)
    save_session(sess)
    try:
        await callback.message.delete()
    except Exception:
        pass
    await callback.answer()

    if not pending:
        await callback.message.answer("Nothing to continue. Send a message.")
        return

    await _send_to_session(callback.message, bot, sess, pending)


@router.callback_query(F.data == "new_session")
async def cb_new_session(callback: CallbackQuery, bot: Bot):
    sess = get_session(callback.from_user.id)
    if not sess:
        await callback.answer("Please /login first.", show_alert=True)
        return

    pending = clear_pending(callback.from_user.id)
    data, error, status = await _create_session(sess)
    if error:
        if _is_auth_failure(status, error):
            delete_session(callback.from_user.id)
            await callback.answer("Your API access is no longer valid.", show_alert=True)
            await _send_welcome(callback.message)
            return
        if pending:
            sess.pending_message = pending
            sess.pending_at = time.time()
            save_session(sess)
        await callback.answer()
        await _send_limit_hint(callback.message, sess, await _config())
        return

    sess.current_session_id = data["id"]
    sess.skip_idle_once = True
    save_session(sess)
    try:
        await callback.message.delete()
    except Exception:
        pass
    await callback.answer("New session started.")

    cfg = await _config()
    if pending:
        await _send_to_session(callback.message, bot, sess, pending)
    else:
        await callback.message.answer(
            _bot_cfg(cfg).get("session_started_text", "New session started."),
            reply_markup=kb.main_menu_keyboard(),
        )


@router.callback_query(F.data.startswith("select_session:"))
async def cb_select_session(callback: CallbackQuery):
    sess = get_session(callback.from_user.id)
    if not sess:
        await callback.answer("Please /login first.", show_alert=True)
        return

    conv_id = callback.data.split(":", 1)[1]
    set_current_session(callback.from_user.id, conv_id)
    clear_pending(callback.from_user.id)
    save_session(sess)
    await callback.answer("Session selected.")
    try:
        await callback.message.edit_text("Session selected. Send your message below.")
    except Exception:
        pass


@router.callback_query(F.data.startswith("delete_session:"))
async def cb_delete_session(callback: CallbackQuery):
    sess = get_session(callback.from_user.id)
    if not sess:
        await callback.answer("Please /login first.", show_alert=True)
        return

    conv_id = callback.data.split(":", 1)[1]
    try:
        await delete_conversation(sess.api_key, conv_id)
    except Exception:
        await callback.answer("Could not delete the session.", show_alert=True)
        return

    if sess.current_session_id == conv_id:
        sess.current_session_id = None
        sess.skip_idle_once = True
        save_session(sess)

    await callback.answer("Deleted.")
    try:
        await callback.message.edit_text("Session deleted.")
    except Exception:
        pass



@router.message(F.text)
async def handle_text(message: Message, bot: Bot):
    if message.text in MENU_TEXTS:
        return

    if (message.text or "").startswith("/"):
        await message.answer("Unknown command. Use /help.")
        return

    sess = get_session(message.from_user.id)
    if not sess:
        await _send_welcome(message)
        return

    cfg = await _config()
    bot_cfg = _bot_cfg(cfg)
    idle_minutes = int(bot_cfg.get("idle_prompt_minutes", 25) or 25)

    if sess.pending_message:
        sess.pending_message = None
        sess.pending_at = None
        sess.skip_idle_once = True
        save_session(sess)

    if not sess.current_session_id:
        data, error, status = await _create_session(sess)
        if error:
            if _is_auth_failure(status, error):
                delete_session(message.from_user.id)
                await _send_welcome(message)
                return
            await _send_limit_hint(message, sess, cfg)
            return
        sess.current_session_id = data["id"]
        save_session(sess)
    else:
        try:
            conv = await get_conversation(sess.api_key, sess.current_session_id)
        except httpx.HTTPStatusError as e:
            if e.response.status_code in (401, 403):
                delete_session(message.from_user.id)
                await _send_welcome(message)
                return
            if e.response.status_code == 404:
                sess.current_session_id = None
                save_session(sess)
                data, error, status = await _create_session(sess)
                if error:
                    if _is_auth_failure(status, error):
                        delete_session(message.from_user.id)
                        await _send_welcome(message)
                        return
                    await _send_limit_hint(message, sess, cfg)
                    return
                sess.current_session_id = data["id"]
                save_session(sess)
            else:
                await message.answer("⚠️ Could not load your session.")
                return
        else:
            if not sess.skip_idle_once and not sess.pending_message:
                try:
                    last = datetime.fromisoformat(
                        conv["last_activity_at"].replace("Z", "+00:00")
                    )
                    idle_seconds = (_now() - last).total_seconds()
                except Exception:
                    idle_seconds = 0

                if idle_seconds >= idle_minutes * 60:
                    sess.pending_message = message.text
                    sess.pending_at = time.time()
                    save_session(sess)
                    await message.answer(
                        bot_cfg.get(
                            "session_prompt_text",
                            "You have been away. Continue the previous session or start a new one?",
                        ),
                        reply_markup=kb.continue_or_new_keyboard(),
                    )
                    return

    sess.skip_idle_once = False
    save_session(sess)
    await _send_to_session(message, bot, sess, message.text)
