import logging
import asyncio
import os
from config import LOG_LEVEL, LOG_FILE, API_ID, API_HASH, BOT_TOKEN
from utils.logging import setup_logging
from pyrogram import Client, filters
from models import init_db

# Import handlers
from bot import commands, dialogs

def cleanup_session():
    """Remove old session files"""
    session_file = "sales_bot.session"
    if os.path.exists(session_file):
        os.remove(session_file)
        logging.info(f"Removed old session file: {session_file}")

# Initialize the client
app = Client(
    "sales_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)

@app.on_message(filters.command("start"))
async def start_command(client, message):
    await message.reply_text("Hello! I'm your sales bot.")

# Add other handlers here...

def main():
    # Setup logging
    setup_logging()
    logger = logging.getLogger(__name__)

    logger.info("Starting Sales Bot...")

    try:
        # Cleanup old session
        cleanup_session()

        # Start the client
        app.run()
        logger.info("Bot started successfully")
    except Exception as e:
        logger.error(f"Error running bot: {e}", exc_info=True)

if __name__ == '__main__':
    main()
