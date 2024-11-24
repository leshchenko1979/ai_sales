import asyncio
import logging

from bot.client import app
from pyrogram import idle
from scheduler import AccountScheduler

logger = logging.getLogger(__name__)


async def main():
    """Main application entry point"""
    try:
        # Initialize scheduler
        scheduler = AccountScheduler()
        await scheduler.start()

        # Start bot
        await app.start()
        logger.info("Bot started")

        # Wait for shutdown using pyrogram.idle()
        try:
            await idle()
        finally:
            # Cleanup
            await scheduler.stop()
            await app.stop()

    except Exception as e:
        logger.error(f"Error in main: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())
