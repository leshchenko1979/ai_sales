# noqa

"""Reset database script."""

import asyncio
import logging
import sys
from pathlib import Path

# Load environment variables
from dotenv import load_dotenv

load_dotenv()

# Add jeeves directory to Python path
root_dir = Path(__file__).parent.parent
sys.path.append(str(root_dir))


logger = logging.getLogger(__name__)


async def reset_database():
    """Reset database by dropping all tables and recreating them."""
    try:
        # Import modules
        from core.accounts.models import Account  # noqa: E402 F401
        from core.db import Base, engine
        from core.messaging.models import Dialog, Message  # noqa: E402 F401

        # Create tables
        logger.info("Dropping all tables...")
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)

        logger.info("Creating database tables...")
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        logger.info("Database reset successfully!")
        return True

    except Exception as e:
        logger.error(f"Error resetting database: {e}", exc_info=True)
        return False


if __name__ == "__main__":
    # Setup logging
    from infrastructure.logging import setup_logging

    setup_logging()

    # Run database reset
    success = asyncio.run(reset_database())
    sys.exit(0 if success else 1)
