import os

from config import API_HASH, API_ID, BOT_TOKEN
from pyrogram import Client

# Initialize the client only if not in testing environment
app = (
    Client(
        "sales_bot",
        api_id=API_ID,
        api_hash=API_HASH,
        bot_token=BOT_TOKEN,
        in_memory=True,  # Prevent session file issues
    )
    if not os.getenv("TESTING")
    else None
)
