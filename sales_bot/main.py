import asyncio
import logging
from contextlib import asynccontextmanager

from bot.client import app
from db.migrate import create_tables
from pyrogram import idle
from scheduler import AccountScheduler

logger = logging.getLogger(__name__)


@asynccontextmanager
async def initialize_services():
    """Initialize and cleanup services using context manager"""
    scheduler = AccountScheduler()
    try:
        await scheduler.start()
        await app.start()
        logger.info("Bot started")
        yield
    finally:
        logger.info("Shutting down services...")
        await scheduler.stop()
        await app.stop()
        logger.info("Cleanup complete")


async def main():
    """Main application entry point"""
    try:
        await create_tables()
        async with initialize_services():
            await idle()
    except Exception as e:
        logger.error(f"Error in main: {e}")
        raise


def run():
    """Entry point with proper loop handling"""
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(main())
    except KeyboardInterrupt:
        logger.info("Received shutdown signal")
    finally:
        loop.close()


if __name__ == "__main__":
    run()
