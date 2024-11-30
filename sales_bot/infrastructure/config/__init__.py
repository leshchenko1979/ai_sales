"""Configuration settings."""

import os
from pathlib import Path
from typing import Final

import dotenv

dotenv.load_dotenv()

# Base paths
ROOT_DIR: Final[Path] = Path(__file__).parent.parent.parent
DATA_DIR: Final[Path] = ROOT_DIR / "data"
LOGS_DIR: Final[Path] = ROOT_DIR / "logs"
EXPORTS_DIR: Final[Path] = ROOT_DIR / "exports"

# Create directories if they don't exist
for directory in [DATA_DIR, LOGS_DIR, EXPORTS_DIR]:
    directory.mkdir(exist_ok=True)

# Application
APP_NAME: Final[str] = "AI Sales Bot"
APP_URL: Final[str] = os.getenv("APP_URL", "https://ai-sales-bot.example.com")

# Database
DATABASE_URL: Final[str] = os.getenv("DATABASE_URL")

# OpenRouter API
OPENROUTER_BASE_API_URL: Final[str] = os.getenv(
    "OPENROUTER_BASE_API_URL", "https://openrouter.ai"
)
OPENROUTER_API_KEY: Final[str] = os.getenv("OPENROUTER_API_KEY")
OPENROUTER_MODEL: Final[str] = os.getenv(
    "OPENROUTER_MODEL", "perplexity/llama-3.1-sonar-large-128k-chat"
)

# OpenAI API
OPENAI_API_KEY: Final[str] = os.getenv("OPENAI_API_KEY")
OPENAI_BASE_API_URL: Final[str] = os.getenv(
    "OPENAI_BASE_API_URL", "https://api.proxyapi.ru/openai/v1"
)
OPENAI_MODEL: Final[str] = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

# AI Provider
DEFAULT_AI_PROVIDER: Final[str] = os.getenv("DEFAULT_AI_PROVIDER", "openai")

# Telegram
API_ID: Final[int] = int(os.getenv("API_ID", "0"))
API_HASH: Final[str] = os.getenv("API_HASH", "")
BOT_TOKEN: Final[str] = os.getenv("BOT_TOKEN", "")
ADMIN_TELEGRAM_ID: Final[int] = int(os.getenv("ADMIN_TELEGRAM_ID", "0"))

# Remote
REMOTE_HOST: Final[str] = os.getenv("REMOTE_HOST", "")
REMOTE_USER: Final[str] = os.getenv("REMOTE_USER", "")

# Account safety settings
MAX_MESSAGES_PER_DAY: Final[int] = int(os.getenv("MAX_MESSAGES_PER_DAY", "30"))
MAX_MESSAGES_PER_HOUR: Final[int] = int(os.getenv("MAX_MESSAGES_PER_HOUR", "5"))
MIN_MESSAGE_DELAY: Final[int] = int(os.getenv("MIN_MESSAGE_DELAY", "60"))  # seconds
RESET_HOUR_UTC: Final[int] = int(
    os.getenv("RESET_HOUR_UTC", "0")
)  # When to reset daily counters
WARMUP_DAYS: Final[int] = int(os.getenv("WARMUP_DAYS", "3"))
WARMUP_MESSAGES: Final[int] = int(os.getenv("WARMUP_MESSAGES", "5"))

# Monitoring
CHECK_INTERVAL: Final[int] = int(os.getenv("CHECK_INTERVAL", str(60 * 5)))  # 5 minutes

# Logging
LOG_LEVEL: Final[str] = os.getenv("LOG_LEVEL", "DEBUG")
LOG_FORMAT: Final[str] = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

# Export settings
MAX_EXPORT_MESSAGES: Final[int] = int(os.getenv("MAX_EXPORT_MESSAGES", "1000"))
EXPORT_DATETIME_FORMAT: Final[str] = "%Y%m%d_%H%M%S"
EXPORT_BATCH_SIZE: Final[int] = int(os.getenv("EXPORT_BATCH_SIZE", "1000"))
EXPORT_CHUNK_SIZE: Final[int] = int(os.getenv("EXPORT_CHUNK_SIZE", "100"))

# Common messages
ERROR_MSG: Final[str] = "Произошла ошибка. Попробуйте позже."
ACCESS_DENIED_MSG: Final[str] = "У вас нет доступа к этой команде."

# Scheduler
SCHEDULER_ON: Final[bool] = False

# Prompts
PROMPTS_PATH: Final[Path] = ROOT_DIR / "core" / "ai" / "sales" / "prompts.yaml"

# Testing
TESTER_TELEGRAM_IDS: Final[list[int]] = []

# Notifications
LESHCHENKO_CHAT_ID: Final[int] = 133526395
