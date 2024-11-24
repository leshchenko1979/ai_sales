import os
from dotenv import load_dotenv

# Загружаем переменные окружения из .env файла
load_dotenv()

# Настройки бота
BOT_TOKEN = os.getenv('BOT_TOKEN')
API_ID = int(os.getenv('API_ID'))
API_HASH = os.getenv('API_HASH')
ADMIN_TELEGRAM_ID = int(os.getenv('ADMIN_TELEGRAM_ID'))

# Настройки OpenRouter
OPENROUTER_API_KEY = os.getenv('OPENROUTER_API_KEY')
OPENROUTER_MODEL = "qwen/qwen-2-7b-instruct:free"
APP_NAME = "SalesBot"
APP_URL = "https://yourapp.com"  # Замените на ваш URL

# Настройки базы данных
DATABASE_URL = os.getenv('DATABASE_URL', 'postgresql://postgres:postgres@localhost:5432/sales_bot')

# Настройки логирования
LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
LOG_FILE = os.getenv('LOG_FILE', '/var/log/sales_bot/app.log')
