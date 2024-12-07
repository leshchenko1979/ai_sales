"""Infrastructure layer for configuration, logging, and other system components."""

from .config import (  # Application; API Keys and Services; Telegram Settings; Safety Settings; Export Settings
    ADMIN_TELEGRAM_ID,
    API_HASH,
    API_ID,
    APP_NAME,
    APP_URL,
    BOT_TOKEN,
    DATABASE_URL,
    EXPORT_BATCH_SIZE,
    EXPORT_CHUNK_SIZE,
    MAX_EXPORT_MESSAGES,
    MAX_MESSAGES_PER_DAY,
    MAX_MESSAGES_PER_HOUR,
    MIN_MESSAGE_DELAY,
    OPENAI_API_KEY,
    OPENAI_MODEL,
    OPENROUTER_API_KEY,
    OPENROUTER_MODEL,
    ROOT_DIR,
    WARMUP_DAYS,
    WARMUP_MESSAGES,
)
from .logging import setup_logging
from .posthog import PosthogClient

__all__ = [
    # Main components
    "setup_logging",
    "PosthogClient",
    # Application constants
    "APP_NAME",
    "APP_URL",
    "ROOT_DIR",
    # API configuration
    "DATABASE_URL",
    "OPENAI_API_KEY",
    "OPENAI_MODEL",
    "OPENROUTER_API_KEY",
    "OPENROUTER_MODEL",
    # Telegram configuration
    "API_ID",
    "API_HASH",
    "BOT_TOKEN",
    "ADMIN_TELEGRAM_ID",
    # Safety limits
    "MAX_MESSAGES_PER_DAY",
    "MAX_MESSAGES_PER_HOUR",
    "MIN_MESSAGE_DELAY",
    "WARMUP_DAYS",
    "WARMUP_MESSAGES",
    # Export configuration
    "EXPORT_BATCH_SIZE",
    "EXPORT_CHUNK_SIZE",
    "MAX_EXPORT_MESSAGES",
]
