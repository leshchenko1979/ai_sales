import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from bot.client import app
from db.migrate import create_tables
from scheduler import AccountScheduler

logger = logging.getLogger(__name__)


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


async def main():
    """Main application entry point"""
    try:
        await create_tables()
        async with initialize_services():
            await app.run()
    except Exception as e:
        logger.error(f"Error in main: {e}")
        raise


@asynccontextmanager
async def initialize_services():
    """Initialize and cleanup services using context manager"""
    # Delete potentially corrupt session file
    session_file = Path("admin_bot.session")
    if session_file.exists():
        try:
            session_file.unlink()  # Delete the file
            logger.info("Deleted existing session file")
        except OSError as e:
            logger.error(f"Failed to delete session file: {e}")

    # Continue with normal initialization
    scheduler = AccountScheduler()
    await scheduler.start()

    try:
        yield scheduler
    finally:
        await scheduler.stop()


if __name__ == "__main__":
    run()
