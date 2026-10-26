"""
Vidhya Bot — Configuration
Loads all environment variables via pydantic-settings.
"""

from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class BotSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    TELEGRAM_BOT_TOKEN: str = ""
    TELEGRAM_BOT_USERNAME: str = "vidhya_hub_bot"

    BACKEND_URL: str = "http://backend:8000"
    SECRET_KEY: str = "CHANGE_ME_generate_with_python_secrets_token_hex_32"

    ADMIN_CHAT_ID: str = ""          # Telegram chat_id for admin alerts (optional)

    APP_URL: str = "http://localhost"
    ENV: str = "development"


@lru_cache
def get_settings() -> BotSettings:
    return BotSettings()
