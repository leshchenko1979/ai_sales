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
ADMIN_TELEGRAM_ID = int(get_env_or_fail('ADMIN_TELEGRAM_ID'))

# OpenRouter settings
OPENROUTER_API_KEY = get_env_or_fail('OPENROUTER_API_KEY')
OPENROUTER_MODEL = "qwen/qwen-2-7b-instruct:free"
APP_NAME = "SalesBot"
APP_URL = "https://yourapp.com"

# Database settings
DATABASE_URL = os.getenv('DATABASE_URL', 'postgresql://postgres:postgres@localhost:5432/sales_bot')

# Logging settings
LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
LOG_FILE = os.getenv('LOG_FILE', '/var/log/sales_bot/app.log')
