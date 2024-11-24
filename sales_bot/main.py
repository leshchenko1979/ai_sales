import asyncio
import logging

from bot.client import app
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

        # Wait for shutdown
        try:
            await app.idle()
        finally:
            # Cleanup
            await scheduler.stop()
            await app.stop()

    except Exception as e:
        logger.error(f"Error in main: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())
