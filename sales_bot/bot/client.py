from telethon import TelegramClient
from config import API_ID, API_HASH, BOT_TOKEN

# Инициализация клиента
client = TelegramClient('sales_bot', API_ID, API_HASH).start(bot_token=BOT_TOKEN)
