import asyncio
import logging
import sys

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import BotCommand

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
    logger.info("Vidhya AI Telegram bot starting")
    bot_info = await bot.get_me()
    logger.info(f"Bot authenticated as: @{bot_info.username}")
    logger.info(f"Backend API URL: {settings.BACKEND_URL}")

    try:
        await bot.set_my_commands(
            [
                BotCommand(command="start", description="Open the assistant"),
                BotCommand(command="login", description="Connect with an API key"),
                BotCommand(command="newchat", description="Start a new session"),
                BotCommand(command="chats", description="My sessions"),
                BotCommand(command="usage", description="Messages and session usage"),
                BotCommand(command="plan", description="My plan"),
                BotCommand(command="logout", description="Disconnect this chat"),
                BotCommand(command="help", description="Commands"),
            ]
        )
    except Exception as e:
        logger.warning(f"Could not set commands: {e}")


async def on_shutdown(bot: Bot):
    logger.info("Bot shutting down...")
    await close_client()


async def main():
    if not settings.TELEGRAM_BOT_TOKEN or settings.TELEGRAM_BOT_TOKEN == "YOUR_BOT_TOKEN_HERE":
        logger.error("TELEGRAM_BOT_TOKEN is missing or invalid. Exiting.")
        sys.exit(1)

    bot = Bot(
        token=settings.TELEGRAM_BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )

    dp = Dispatcher()
    dp.include_router(router)
    
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)

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
