"""
Vidhya Bot — Telegram Bot Entry Point (Phase 6)
Initializes Aiogram Bot, Dispatcher, and starts long-polling.
"""

import asyncio
import logging
import sys

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import MenuButtonWebApp, WebAppInfo

from config import get_settings
from api_client import close_client
from handlers import router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger("vidhya.bot")
settings = get_settings()


async def on_startup(bot: Bot):
    logger.info("═" * 50)
    logger.info("  VIDHYA BOT — Telegram Bot Starting (Phase 6)")
    logger.info("═" * 50)
    
    bot_info = await bot.get_me()
    logger.info(f"Bot authenticated as: @{bot_info.username}")
    logger.info(f"Backend API URL: {settings.BACKEND_URL}")
    
    # Set the bot menu button to open the Web App (passes initData correctly)
    webapp_url = f"{settings.APP_URL}/user"
    try:
        await bot.set_chat_menu_button(
            menu_button=MenuButtonWebApp(text="📊 Dashboard", web_app=WebAppInfo(url=webapp_url))
        )
        logger.info(f"Menu button set to WebApp: {webapp_url}")
    except Exception as e:
        logger.warning(f"Could not set menu button: {e}")


async def on_shutdown(bot: Bot):
    logger.info("Bot shutting down...")
    await close_client()


async def main():
    if not settings.TELEGRAM_BOT_TOKEN or settings.TELEGRAM_BOT_TOKEN == "YOUR_BOT_TOKEN_HERE":
        logger.error("TELEGRAM_BOT_TOKEN is missing or invalid. Exiting.")
        sys.exit(1)

    # Initialize bot with default parse mode
    bot = Bot(
        token=settings.TELEGRAM_BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )

    # Initialize dispatcher
    dp = Dispatcher()
    dp.include_router(router)
    
    # Register lifecycle hooks
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)

    # Start long polling
    try:
        await bot.delete_webhook(drop_pending_updates=True)
        await dp.start_polling(bot)
    except Exception as e:
        logger.error(f"Error during polling: {e}")
    finally:
        await bot.session.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot stopped by user.")
