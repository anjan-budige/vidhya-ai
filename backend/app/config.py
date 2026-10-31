from functools import lru_cache
from typing import List

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Central configuration — all values from .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    ENV: str = "development"
    DEBUG: bool = True
    LOG_LEVEL: str = "INFO"
    APP_NAME: str = "Vidhya Bot"
    APP_URL: str = "http://localhost"

    SETTINGS_ENCRYPTION_KEY: str = ""
    PAYMENTS_ENCRYPTION_KEY: str = ""
    # Demo checkout is always available outside production; set this to true to
    # allow it in production for a controlled test (admin must still activate it).
    PAYMENTS_DEMO_ENABLED: bool = False

    RESEND_API_KEY: str = ""
    RESEND_FROM_EMAIL: str = ""
    RESEND_FROM_NAME: str = "Vidhya AI"
    RESEND_REPLY_TO: str = ""
    SUPERADMIN_EMAIL: str = "admin@example.com"

    POSTGRES_USER: str = "vidhya"
    POSTGRES_PASSWORD: str = "CHANGE_ME"
    POSTGRES_DB: str = "vidhya_db"
    POSTGRES_HOST: str = "postgres"
    POSTGRES_PORT: int = 5432
    DATABASE_URL: str = "postgresql+asyncpg://vidhya:CHANGE_ME@postgres:5432/vidhya_db"
    DATABASE_URL_SYNC: str = "postgresql://vidhya:CHANGE_ME@postgres:5432/vidhya_db"

    DB_POOL_SIZE: int = 10
    DB_MAX_OVERFLOW: int = 20
    DB_POOL_RECYCLE: int = 300
    DB_ECHO: bool = False

    REDIS_URL: str = "redis://redis:6379/0"
    REDIS_CELERY_BROKER: str = "redis://redis:6379/1"
    REDIS_CELERY_BACKEND: str = "redis://redis:6379/2"
    REDIS_MAX_CONNECTIONS: int = 20

    MINIO_ROOT_USER: str = "minioadmin"
    MINIO_ROOT_PASSWORD: str = "CHANGE_ME"
    MINIO_ENDPOINT: str = "http://minio:9000"
    MINIO_EXTERNAL_ENDPOINT: str = "http://localhost:9000"
    MINIO_BUCKET: str = "vidhya-documents"
    MINIO_REGION: str = "us-east-1"

    TELEGRAM_BOT_TOKEN: str = ""
    TELEGRAM_BOT_USERNAME: str = "vidhya_bot"

    ADMIN_DEFAULT_USERNAME: str = "admin"
    ADMIN_DEFAULT_PASSWORD: str = "CHANGE_ME"
    ADMIN_TOTP_SECRET: str = ""
    ADMIN_TOTP_ENABLED: bool = False
    ADMIN_MAX_FAILED_LOGINS: int = 5
    ADMIN_LOCKOUT_MINUTES: int = 15

    SECRET_KEY: str = "CHANGE_ME_generate_with_python_secrets_token_hex_32"
    CSRF_SECRET: str = "CHANGE_ME_generate_with_python_secrets_token_hex_32"
    CORS_ORIGINS: str = "http://localhost,http://localhost:3000,http://localhost:5173"

    SESSION_EXPIRY_SECONDS: int = 3600  # 1 hour
    ADMIN_SESSION_EXPIRY_SECONDS: int = 1800  # 30 minutes
    SESSION_COOKIE_NAME: str = "vidhya_session"
    SESSION_COOKIE_SECURE: bool = False  # True in production
    SESSION_COOKIE_HTTPONLY: bool = True
    SESSION_COOKIE_SAMESITE: str = "Strict"

    CELERY_BROKER_URL: str = "redis://redis:6379/1"
    CELERY_RESULT_BACKEND: str = "redis://redis:6379/2"
    CELERY_WORKER_CONCURRENCY: int = 2

    RATE_LIMIT_AI_PER_MINUTE: int = 60
    RATE_LIMIT_LOGIN_PER_MINUTE: int = 5
    RATE_LIMIT_UPLOAD_PER_HOUR: int = 10

    MAX_UPLOAD_SIZE_MB: int = 100
    ALLOWED_MIME_TYPES: str = (
        "application/pdf,text/plain,text/markdown,text/csv,application/json"
    )
    CHUNK_SIZE: int = 500  # tokens per chunk
    CHUNK_OVERLAP: int = 50  # overlap between chunks

    # Cosine-similarity floor for retrieval. Chunks below this are unrelated to
    # the question, and citing them reads as noise to the user.
    RAG_MIN_SCORE: float = 0.45
    RAG_TOP_K: int = 5
    # A chunk is only cited when the finished answer is itself similar to it,
    # which is what separates "used this passage" from "was vaguely nearby".
    RAG_ANSWER_MIN_SCORE: float = 0.5
    RAG_ANSWER_FALLBACK_SCORE: float = 0.65
    # "grounded" cites only chunks the answer used; "inserted" cites every
    # chunk that made it into the prompt.
    RAG_CITATION_MODE: str = "grounded"

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def parse_cors_origins(cls, v: str) -> str:
        """Keep as string — parsed to list in property."""
        return v

    @property
    def cors_origins_list(self) -> List[str]:
        """Parse CORS_ORIGINS string into list."""
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",")]

    @property
    def max_upload_size_bytes(self) -> int:
        """Convert MB to bytes."""
        return self.MAX_UPLOAD_SIZE_MB * 1024 * 1024

    @property
    def allowed_mime_types_list(self) -> List[str]:
        """Parse allowed MIME types."""
        return [t.strip() for t in self.ALLOWED_MIME_TYPES.split(",")]

    @property
    def is_production(self) -> bool:
        return self.ENV == "production"

    @property
    def payments_demo_allowed(self) -> bool:
        return self.PAYMENTS_DEMO_ENABLED or not self.is_production

    @property
    def is_development(self) -> bool:
        return self.ENV == "development"


@lru_cache()
def get_settings() -> Settings:
    """Cached settings instance — created once per process."""
    return Settings()
