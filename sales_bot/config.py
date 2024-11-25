import os


def get_env_or_fail(key: str) -> str:
    value = os.getenv(key)
    if value is None:
        raise ValueError(f"Environment variable {key} is not set")
    return value


# Pyrogram settings
API_ID = int(get_env_or_fail("API_ID"))
API_HASH = get_env_or_fail("API_HASH")
BOT_TOKEN = get_env_or_fail("BOT_TOKEN")

# Bot settings
ADMIN_TELEGRAM_ID = int(get_env_or_fail("ADMIN_TELEGRAM_ID"))

# OpenRouter settings
OPENROUTER_API_KEY = get_env_or_fail("OPENROUTER_API_KEY")
OPENROUTER_MODEL = "qwen/qwen-2-7b-instruct:free"
APP_NAME = "SalesBot"
APP_URL = "https://yourapp.com"

# Database settings
DATABASE_URL = os.getenv(
    "DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/sales_bot"
)

# Logging settings
LOG_LEVEL = os.getenv("LOG_LEVEL", "DEBUG")
LOG_FILE = os.getenv("LOG_FILE", "/var/log/sales_bot/app.log")

# Safety settings
MIN_MESSAGE_DELAY = 30  # Minimum delay between messages in seconds
MAX_MESSAGES_PER_HOUR = 20  # Maximum messages per hour per account
MAX_MESSAGES_PER_DAY = 50  # Maximum messages per day per account
RESET_HOUR_UTC = 0  # Hour in UTC when daily counters reset
WARMUP_PERIOD_DAYS = 7  # Days between account warmups
WARMUP_MESSAGE_COUNT = 3  # Number of messages to send during warmup

# Account rotation settings
ROTATION_INTERVAL = 60  # Minutes between account rotations
ACCOUNT_REST_HOURS = 12  # Hours an account should rest after reaching daily limit

# Monitoring settings
MONITORING_INTERVAL = 15  # Minutes between account status checks
BLOCK_CHECK_INTERVAL = 60  # Minutes between block checks

# Safety thresholds
MAX_ERRORS_BEFORE_DISABLE = 3  # Maximum consecutive errors before disabling account
ERROR_RESET_HOURS = 24  # Hours after which error count resets
