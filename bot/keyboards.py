"""Vidhya Bot — Keyboard Builders"""

from aiogram.types import (
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    ReplyKeyboardMarkup,
    KeyboardButton,
)


def main_menu_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="💬 Ask AI"), KeyboardButton(text="🆕 New Chat")],
            [KeyboardButton(text="📋 My Sessions"), KeyboardButton(text="🗑️ Delete Session")],
            [KeyboardButton(text="⚡ Usage"), KeyboardButton(text="📊 My Plan")],
            [KeyboardButton(text="❓ Help")],
        ],
        resize_keyboard=True,
        input_field_placeholder="Type your question...",
    )


def continue_or_new_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="▶️ Continue session", callback_data="continue_session"),
                InlineKeyboardButton(text="🆕 New session", callback_data="new_session"),
            ]
        ]
    )


def sessions_keyboard(convs: list) -> InlineKeyboardMarkup:
    buttons = []
    for conv in convs[:10]:
        title = (conv.get("title") or "Chat")[:32]
        buttons.append(
            [
                InlineKeyboardButton(
                    text=f"💬 {title}",
                    callback_data=f"select_session:{conv['id']}",
                )
            ]
        )
    buttons.append([InlineKeyboardButton(text="❌ Cancel", callback_data="cancel")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def delete_sessions_keyboard(convs: list) -> InlineKeyboardMarkup:
    buttons = []
    for conv in convs[:10]:
        title = (conv.get("title") or "Chat")[:30]
        buttons.append(
            [
                InlineKeyboardButton(
                    text=f"🗑️ {title}",
                    callback_data=f"delete_session:{conv['id']}",
                )
            ]
        )
    buttons.append([InlineKeyboardButton(text="❌ Cancel", callback_data="cancel")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def cancel_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="❌ Cancel", callback_data="cancel")]]
    )
