from pyrogram import Client

from ..config import API_HASH, API_ID, BOT_TOKEN

app = Client("sales_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)
