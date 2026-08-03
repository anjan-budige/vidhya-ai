"""
Vidhya Bot — Keyboard Builders
All InlineKeyboardMarkup and ReplyKeyboardMarkup definitions.
"""

from aiogram.types import (
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    ReplyKeyboardMarkup,
    KeyboardButton,
    WebAppInfo,
)

from config import get_settings

settings = get_settings()


# ── Main Menu (reply keyboard) ────────────────────────────────────────────────

def main_menu_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="💬 Ask AI"), KeyboardButton(text="📊 My Plan")],
            [KeyboardButton(text="🆕 New Chat"), KeyboardButton(text="📋 My Chats")],
            [KeyboardButton(text="🗑️ Delete Chat"), KeyboardButton(text="⚡ Usage")],
        ],
        resize_keyboard=True,
        input_field_placeholder="Type your question or pick an option...",
    )


# ── Plan upgrade inline keyboard ──────────────────────────────────────────────

def upgrade_plans_keyboard(plans: list, current_price: float = 0) -> InlineKeyboardMarkup:
    """Builds inline buttons for each paid plan."""
    buttons = []
    plan_emoji = {"basic": "🥈", "standard": "🥇", "premium": "💎"}

    for plan in plans:
        name = plan.get("name", "")
        if name == "free":
            continue
        price = plan.get("price_inr", 0)
        emoji = plan_emoji.get(name, "📦")
        
        if price <= current_price:
            buttons.append([
                InlineKeyboardButton(
                    text=f"✅ {name.capitalize()} (Active)" if price == current_price else f"✅ {name.capitalize()}",
                    callback_data="ignore"
                )
            ])
        else:
            buttons.append([
                InlineKeyboardButton(
                    text=f"{emoji} Upgrade to {name.capitalize()} — ₹{price}/mo",
                    callback_data=f"buy_plan:{plan['id']}"
                )
            ])

    buttons.append([
        InlineKeyboardButton(text="🔙 Cancel", callback_data="cancel")
    ])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


# ── Payment confirmation keyboard ─────────────────────────────────────────────

def payment_keyboard(payment_url: str, plan_name: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=f"💳 Pay for {plan_name.capitalize()} Plan",
            url=payment_url
        )],
        [InlineKeyboardButton(text="✅ I've paid", callback_data="check_payment")],
        [InlineKeyboardButton(text="❌ Cancel", callback_data="cancel")],
    ])


# ── Open Web App keyboard ─────────────────────────────────────────────────────

def open_webapp_keyboard() -> InlineKeyboardMarkup:
    webapp_url = f"{settings.APP_URL}/user"
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="🌐 Open Vidhya Dashboard",
            web_app=WebAppInfo(url=webapp_url)
        )],
    ])


# ── Conversation list keyboard ────────────────────────────────────────────────

def conversations_keyboard(convs: list) -> InlineKeyboardMarkup:
    buttons = []
    for conv in convs[:5]:  # Show max 5
        title = conv.get("title", "Chat")[:30]
        cid = conv["id"]
        status = "🟢" if conv.get("status") == "active" else "⚪"
        buttons.append([
            InlineKeyboardButton(
                text=f"{status} {title}",
                callback_data=f"switch_conv:{cid}"
            )
        ])
    buttons.append([InlineKeyboardButton(text="🔙 Back", callback_data="cancel")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


# ── Delete conversation list keyboard ──────────────────────────────────────────

def delete_conversations_keyboard(convs: list) -> InlineKeyboardMarkup:
    buttons = []
    for conv in convs[:10]:  # Show max 10
        title = conv.get("title", "Chat")[:30]
        cid = conv["id"]
        buttons.append([
            InlineKeyboardButton(
                text=f"🗑️ Delete: {title}",
                callback_data=f"delete_conv:{cid}"
            )
        ])
    buttons.append([InlineKeyboardButton(text="🔙 Cancel", callback_data="cancel")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


# ── Single close button ───────────────────────────────────────────────────────

def close_keyboard(conv_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔒 Close this chat", callback_data=f"close_conv:{conv_id}")],
        [InlineKeyboardButton(text="🔙 Cancel", callback_data="cancel")],
    ])


# ── Cancel only ───────────────────────────────────────────────────────────────

def cancel_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Cancel", callback_data="cancel")]
    ])
