import logging
import asyncio
from config import LOG_LEVEL, LOG_FILE, API_ID, API_HASH, BOT_TOKEN
from utils.logging import setup_logging
from pyrogram import Client, filters

# Import handlers
from bot import commands, dialogs

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
        # Start the client
        app.run()
        logger.info("Bot started successfully")
    except Exception as e:
        logger.error(f"Error running bot: {e}")

if __name__ == '__main__':
    main()
