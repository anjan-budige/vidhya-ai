"""
Vidhya Bot — Handlers
Handles all commands, callback queries, and text messages.
"""

import logging
import math
import httpx
from datetime import datetime, timezone, timedelta
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.filters import CommandStart, Command
from aiogram.utils.chat_action import ChatActionSender

from api_client import (
    get_plans,
    get_my_subscription,
    get_ai_quota,
    create_conversation,
    list_conversations,
    close_conversation,
    delete_conversation,
    initiate_payment,
    stream_ai_response,
)
from auth_middleware import ensure_session
from session_store import set_active_conversation, get_session, save_session
import keyboards as kb

logger = logging.getLogger("vidhya.handlers")

router = Router()

# ── Command Handlers ──────────────────────────────────────────────────────────

@router.message(CommandStart())
async def cmd_start(message: Message):
    """
    Handles /start command.
    Ensures user is registered and has a valid backend session.
    """
    sess = await ensure_session(
        message.from_user.id,
        message.from_user.first_name,
        message.from_user.username,
        force_refresh=True
    )
    if not sess:
        await message.answer("⚠️ Sorry, I couldn't connect to the backend system right now.")
        return

    welcome_text = (
        f"👋 Welcome to *Vidhya Bot*, {message.from_user.first_name}!\n\n"
        "I am your AI-powered educational assistant. I can help you with your studies, "
        "answer questions, and analyze documents.\n\n"
        f"You are currently on the *{sess.plan_name.capitalize()}* plan.\n\n"
        "How can I help you today?"
    )
    await message.answer(welcome_text, reply_markup=kb.main_menu_keyboard(), parse_mode="Markdown")


@router.message(F.text == "❓ Help")
@router.message(Command("help"))
async def cmd_help(message: Message):
    help_text = (
        "📚 *Vidhya Bot Commands*\n\n"
        "💬 *Ask AI* — Send me any question, and I'll answer it.\n"
        "🆕 *New Chat* — Start a fresh conversation context.\n"
        "📋 *My Chats* — View and switch between your recent conversations.\n"
        "🗑️ *Delete Chat* — Delete a conversation and its history.\n"
        "📊 *My Plan* — View your subscription plan and upgrade options.\n"
        "⚡ *Usage* — Check your AI usage and remaining quota.\n"
        "🌐 *Open Vidhya Dashboard* — Open the mini web app to manage your account.\n"
    )
    await message.answer(help_text, reply_markup=kb.main_menu_keyboard(), parse_mode="Markdown")


@router.message(F.text == "🆕 New Chat")
@router.message(Command("newchat"))
async def cmd_newchat(message: Message):
    sess = await ensure_session(message.from_user.id, message.from_user.first_name, message.from_user.username)
    if not sess:
        return

    try:
        data = await create_conversation(sess.session_token)
        conv_id = data["id"]
        set_active_conversation(message.from_user.id, conv_id)
        
        await message.answer(
            "✅ Started a new conversation!\n"
            "The context has been cleared. What would you like to discuss?",
            reply_markup=kb.main_menu_keyboard()
        )
    except httpx.HTTPStatusError as e:
        err_msg = "⚠️ Failed to start a new chat."
        if e.response.status_code == 400:
            try:
                err_msg = f"⚠️ {e.response.json().get('detail', err_msg)}"
            except Exception:
                pass
        await message.answer(err_msg)
    except Exception as e:
        logger.error(f"Failed to create conversation: {e}")
        await message.answer("⚠️ Failed to start a new chat. You might have reached your active chat limit.")


@router.message(F.text == "📋 My Chats")
async def cmd_mychats(message: Message):
    sess = await ensure_session(message.from_user.id, message.from_user.first_name, message.from_user.username)
    if not sess:
        return

    try:
        convs = await list_conversations(sess.session_token)
        if not convs:
            await message.answer("You don't have any active chats.")
            return
            
        await message.answer(
            "Here are your recent conversations. Select one to switch:",
            reply_markup=kb.conversations_keyboard(convs)
        )
    except Exception as e:
        logger.error(f"Failed to list conversations: {e}")
        await message.answer("⚠️ Failed to load your chats.")


@router.message(F.text == "🗑️ Delete Chat")
@router.message(Command("deletechat"))
async def cmd_deletechat(message: Message):
    sess = await ensure_session(message.from_user.id, message.from_user.first_name, message.from_user.username)
    if not sess:
        return

    try:
        convs = await list_conversations(sess.session_token)
        if not convs:
            await message.answer("You don't have any active chats to delete.")
            return
            
        await message.answer(
            "Select a conversation to permanently delete:",
            reply_markup=kb.delete_conversations_keyboard(convs)
        )
    except Exception as e:
        logger.error(f"Failed to list conversations for deletion: {e}")
        await message.answer("⚠️ Failed to load your chats.")


@router.message(F.text == "📊 My Plan")
@router.message(Command("plan"))
async def cmd_plan(message: Message):
    sess = await ensure_session(message.from_user.id, message.from_user.first_name, message.from_user.username)
    if not sess:
        return

    try:
        sub = await get_my_subscription(sess.session_token)
        plans = await get_plans()
        
        raw_plan_name = sub.get("plan_name", "free").lower()
        plan_name = sub.get("plan_display_name", sub.get("plan_name", "free")).capitalize()
        status = sub.get("status", "unknown").capitalize()
        
        daily_used = sub.get("daily_messages_used", 0)
        daily_limit = sub.get("daily_messages_limit", 1)
        monthly_used = sub.get("monthly_messages_used", 0)
        monthly_limit = sub.get("monthly_messages_limit", 0)
        active_convs = sub.get("active_conversations", 0)
        max_convs = sub.get("max_active_conversations", 1)
        
        plan_snapshot = sub.get("plan_snapshot") or {}
        current_price = plan_snapshot.get("price_inr", 0)
        
        text = f"📊 *Your Subscription Details*\n\n"
        text += f"🏷️ *Plan:* {plan_name}\n"
        text += f"⚡ *Status:* {status}\n\n"
        
        started_at = sub.get("started_at")
        if started_at:
            try:
                s_dt = datetime.fromisoformat(started_at.replace("Z", "+00:00"))
                # Convert to IST
                s_dt_ist = s_dt.astimezone(timezone(timedelta(hours=5, minutes=30)))
                text += f"🗓️ *Purchased On:* {s_dt_ist.strftime('%b %d, %Y')}\n"
            except:
                pass
                
        expires_at = sub.get("expires_at")
        
        if raw_plan_name == "free":
            text += f"⏳ *Validity:* Lifetime\n"
        elif expires_at:
            try:
                e_dt = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
                e_dt_ist = e_dt.astimezone(timezone(timedelta(hours=5, minutes=30)))
                now_ist = datetime.now(timezone(timedelta(hours=5, minutes=30)))
                days_left = max(0, (e_dt_ist.date() - now_ist.date()).days)
                
                if days_left == 0:
                    validity_str = f"Expires today ({e_dt_ist.strftime('%b %d, %Y')})"
                elif days_left == 1:
                    validity_str = f"1 day left (Expires {e_dt_ist.strftime('%b %d, %Y')})"
                else:
                    validity_str = f"{days_left} days left (Expires {e_dt_ist.strftime('%b %d, %Y')})"
                    
                text += f"⏳ *Validity:* {validity_str}\n"
            except:
                pass
        else:
            text += f"⏳ *Validity:* Lifetime\n"
            
        text += f"\n📈 *Usage & Limits:*\n"
        text += f"• Daily Messages: {daily_used} / {daily_limit}\n"
        text += f"• Monthly Messages: {monthly_used} / {monthly_limit}\n"
        text += f"• Active Chats: {active_convs} / {max_convs}\n\n"
        
        text += "Do you want to upgrade your plan?"
        
        await message.answer(text, reply_markup=kb.upgrade_plans_keyboard(plans, current_price), parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Failed to get plan info: {e}")
        await message.answer("⚠️ Failed to load plan information.")


@router.message(F.text == "⚡ Usage")
@router.message(Command("usage"))
async def cmd_usage(message: Message):
    sess = await ensure_session(message.from_user.id, message.from_user.first_name, message.from_user.username)
    if not sess:
        return

    try:
        quota = await get_ai_quota(sess.session_token)
        
        daily_msgs = quota.get("daily_messages_used", 0)
        max_daily_msgs = quota.get("daily_messages_limit", 0)
        
        monthly_msgs = quota.get("monthly_messages_used", 0)
        max_monthly_msgs = quota.get("monthly_messages_limit", 0)
        
        text = "⚡ *Your AI Usage*\n\n"
        text += f"Daily Messages: {daily_msgs} / {max_daily_msgs}\n"
        text += f"Monthly Messages: {monthly_msgs} / {max_monthly_msgs}\n\n"
        text += "_Quota resets at midnight IST._"
        
        await message.answer(text, parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Failed to get usage info: {e}")
        await message.answer("⚠️ Failed to load usage information.")


# ── Callback Handlers ─────────────────────────────────────────────────────────

@router.callback_query(F.data == "cancel")
async def cq_cancel(callback: CallbackQuery):
    await callback.message.delete()
    await callback.answer("Cancelled.")


@router.callback_query(F.data.startswith("switch_conv:"))
async def cq_switch_conv(callback: CallbackQuery):
    conv_id = callback.data.split(":")[1]
    set_active_conversation(callback.from_user.id, conv_id)
    
    await callback.message.edit_text("✅ Switched to conversation.")
    await callback.answer()


@router.callback_query(F.data.startswith("delete_conv:"))
async def cq_delete_conv(callback: CallbackQuery):
    conv_id = callback.data.split(":")[1]
    sess = await ensure_session(callback.from_user.id, callback.from_user.first_name, callback.from_user.username)
    if not sess:
        await callback.answer("Session error.", show_alert=True)
        return

    try:
        await delete_conversation(sess.session_token, conv_id)
        
        # If the deleted conversation was the active one, clear it
        if sess.active_conv_id == conv_id:
            set_active_conversation(callback.from_user.id, None)
            
        await callback.message.edit_text("✅ Conversation deleted permanently.")
        await callback.answer()
    except httpx.HTTPStatusError as e:
        err_msg = "⚠️ Failed to delete conversation."
        try:
            err_msg = f"⚠️ {e.response.json().get('detail', err_msg)}"
        except Exception:
            pass
        logger.error(f"Failed to delete conversation: HTTP {e.response.status_code} - {err_msg}")
        await callback.answer(err_msg, show_alert=True)
    except Exception as e:
        logger.error(f"Failed to delete conversation: {e}")
        await callback.answer("⚠️ Failed to delete conversation.", show_alert=True)


@router.callback_query(F.data.startswith("buy_plan:"))
async def cq_buy_plan(callback: CallbackQuery):
    plan_id = callback.data.split(":")[1]
    sess = await ensure_session(callback.from_user.id, callback.from_user.first_name, callback.from_user.username)
    if not sess:
        await callback.answer("Session error.", show_alert=True)
        return

    try:
        # Get plans to find the amount
        plans = await get_plans()
        plan = next((p for p in plans if p["id"] == plan_id), None)
        if not plan:
            await callback.answer("Plan not found.", show_alert=True)
            return

        # Initiate payment
        amount_paise = plan["price_inr"] * 100
        payment = await initiate_payment(sess.session_token, plan_id, amount_paise)
        payment_url = payment.get("payment_url")
        
        if payment_url:
            await callback.message.edit_text(
                f"💳 Proceed to pay ₹{plan['price_inr']} for the *{plan['name'].capitalize()}* plan.\n\n"
                "Click the button below to complete your payment.",
                reply_markup=kb.payment_keyboard(payment_url, plan["name"]),
                parse_mode="Markdown"
            )
        else:
            await callback.answer("Failed to generate payment URL.", show_alert=True)
            
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 409:
            err_detail = e.response.json().get("detail", "Plan conflict.")
            await callback.answer(err_detail, show_alert=True)
        else:
            logger.error(f"Payment initiation HTTP error: {e}")
            await callback.answer("⚠️ Failed to initiate payment.", show_alert=True)
    except Exception as e:
        logger.error(f"Payment initiation failed: {e}")
        await callback.answer("⚠️ Failed to initiate payment.", show_alert=True)


@router.callback_query(F.data == "check_payment")
async def cq_check_payment(callback: CallbackQuery):
    # In a real scenario, this could check the backend for payment status,
    # but the backend will activate via webhook. So we just inform the user.
    await callback.answer("Checking payment status... If successful, you will receive a confirmation message.", show_alert=True)
    await callback.message.delete()


# ── AI Message Handler ────────────────────────────────────────────────────────

@router.message(F.text)
async def handle_ai_message(message: Message, bot: Bot):
    """
    Catch-all text handler.
    If it's not a command or menu button, treat it as a message to the AI.
    Streams the SSE response back to the user by editing the message.
    """
    # Ignore "💬 Ask AI" placeholder text
    if message.text == "💬 Ask AI":
        await message.answer("Just type your question here! ⬇️")
        return

    sess = await ensure_session(message.from_user.id, message.from_user.first_name, message.from_user.username)
    if not sess:
        await message.answer("⚠️ Session error. Please /start again.")
        return

    # Ensure active conversation exists
    if not sess.active_conv_id:
        try:
            data = await create_conversation(sess.session_token)
            set_active_conversation(message.from_user.id, data["id"])
        except httpx.HTTPStatusError as e:
            err_msg = "⚠️ Failed to start a chat session. Please use /newchat."
            if e.response.status_code == 400:
                try:
                    err_msg = f"⚠️ {e.response.json().get('detail', err_msg)}\nUse /deletechat to free up space."
                except Exception:
                    pass
            await message.answer(err_msg)
            return
        except Exception as e:
            logger.error(f"Auto-create conv failed: {e}")
            await message.answer("⚠️ Failed to start a chat session. Please use /newchat.")
            return

    # Send typing action
    async with ChatActionSender.typing(bot=bot, chat_id=message.chat.id):
        # Create an initial placeholder message
        reply_msg = await message.answer("⏳ _Thinking..._", parse_mode="Markdown")

        full_response = ""
        last_edit_time = 0
        import time

        try:
            # Stream SSE events
            async for token in stream_ai_response(
                sess.session_token,
                message.text,
                sess.active_conv_id
            ):
                if token.startswith("\n\n⚠️"):
                    # Error propagated from SSE
                    full_response += token
                    break

                full_response += token
                
                # Throttle message edits to avoid Telegram rate limits (1 edit per second)
                current_time = time.time()
                if current_time - last_edit_time > 1.0:
                    try:
                        await reply_msg.edit_text(f"{full_response} ⏳")
                        last_edit_time = current_time
                    except Exception:
                        pass # Ignore temporary edit errors

            # Final edit to remove hourglass
            if full_response.strip():
                try:
                    await reply_msg.edit_text(full_response, parse_mode="Markdown")
                except Exception:
                    await reply_msg.edit_text(full_response)
            else:
                await reply_msg.edit_text("⚠️ No response from AI.")

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 400:
                err_json = e.response.json()
                if "closed" in str(err_json) or "timed out" in str(err_json):
                    # Conversation timed out on the backend, clear the bot session's active_conv_id
                    sess.active_conv_id = None
                    save_session(sess)
                    await reply_msg.edit_text("⚠️ Your previous session timed out. I have started a new one for you! Please send your message again.")
                    return
            logger.error(f"AI Stream HTTP Error: {e}")
            await reply_msg.edit_text("⚠️ An error occurred while communicating with the AI.")
            return

        except Exception as e:
            logger.error(f"AI Stream error: {e}")
            await reply_msg.edit_text("⚠️ An error occurred while generating the response.")
            return
