import asyncio
import logging
from pathlib import Path

from bot.client import app
from db.migrate import create_tables
from pyrogram import idle
from scheduler import AccountScheduler
from utils.logging import setup_logging

logger = logging.getLogger(__name__)


async def main():
    """Main application entry point"""
    try:
        setup_logging()
        await create_tables()

        # Delete potentially corrupt session file
        session_file = Path("admin_bot.session")
        if session_file.exists():
            try:
                session_file.unlink()  # Delete the file
                logger.info("Deleted existing session file")
            except OSError as e:
                logger.error(f"Failed to delete session file: {e}")

        try:
            await app.start()
            scheduler = AccountScheduler()
            await scheduler.start()

            await idle()

        finally:
            await scheduler.stop()
            await app.stop()

    except Exception as e:
        logger.error(f"Error in main: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    asyncio.run(main())
