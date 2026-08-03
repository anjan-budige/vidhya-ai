"""
Vidhya Bot — Configuration
Loads all environment variables via pydantic-settings.
"""

from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class BotSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Telegram
    TELEGRAM_BOT_TOKEN: str = ""
    TELEGRAM_BOT_USERNAME: str = "vidhya_hub_bot"

    # Backend API
    BACKEND_URL: str = "http://backend:8000"

    # Admin notification chat
    ADMIN_CHAT_ID: str = ""          # Telegram chat_id for admin alerts (optional)

    # App
    APP_URL: str = "http://localhost"
    ENV: str = "development"


@lru_cache
def get_settings() -> BotSettings:
    return BotSettings()
