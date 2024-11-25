import os

from config import API_HASH, API_ID, BOT_TOKEN
from pyrogram import Client, filters

# Initialize the client only if not in testing environment
app = (
    Client(
        "sales_bot",
        api_id=API_ID,
        api_hash=API_HASH,
        bot_token=BOT_TOKEN,
        in_memory=True,  # Prevent session file issues
        parse_mode="markdown",  # Enable markdown parsing by default
        workers=4,  # Number of worker threads
    )
    if not os.getenv("TESTING")
    else None
)


# Add this to ensure commands work in private chats only
def private_filter(_, __, message):
    """Filter for private messages only"""
    return bool(message.chat and message.chat.type == "private")


filters.private = filters.create(private_filter)
