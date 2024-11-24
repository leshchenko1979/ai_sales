import logging
import os
from config import LOG_LEVEL, LOG_FILE, API_ID, API_HASH, BOT_TOKEN
from utils.logging import setup_logging
from pyrogram import Client
from models import init_db
from bot.client import init_client

def cleanup_session():
    """Remove old session files"""
    session_file = "sales_bot.session"
    if os.path.exists(session_file):
        os.remove(session_file)
        logging.info(f"Removed old session file: {session_file}")

def main():
    # Setup logging
    setup_logging()
    logger = logging.getLogger(__name__)

    logger.info("Starting Sales Bot...")

    try:
        # Cleanup old session
        cleanup_session()

        # Initialize the client
        app = init_client(API_ID, API_HASH, BOT_TOKEN)

        # Import handlers after client initialization
        from bot import commands, dialogs

        # Start the client
        app.run()
        logger.info("Bot started successfully")
    except Exception as e:
        logger.error(f"Error running bot: {e}", exc_info=True)

if __name__ == '__main__':
    main()
