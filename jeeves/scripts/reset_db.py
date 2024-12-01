# noqa

"""Database migration script."""

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


async def migrate_database():
    """Create missing tables and relationships."""
    try:
        # Import modules
        from core.accounts.models.account import Account  # noqa: F401
        from core.accounts.models.profile import (  # noqa: F401
            AccountProfile,
            ProfileHistory,
            ProfileTemplate,
        )
        from core.db import Base, engine
        from core.messaging.models import Dialog, Message  # noqa: F401
        from sqlalchemy import inspect, text

        # Get inspector to check existing tables
        async with engine.begin() as conn:
            # Get existing tables
            existing_tables = await conn.run_sync(
                lambda sync_conn: inspect(sync_conn).get_table_names()
            )

            # Create missing tables
            logger.info("Checking database tables...")
            for table_name, table in Base.metadata.tables.items():
                if table_name not in existing_tables:
                    logger.info(f"Creating table {table_name}...")
                    await conn.run_sync(lambda sync_conn: table.create(sync_conn))
                else:
                    logger.info(f"Table {table_name} already exists")

            # Ensure sequences are in sync
            for table_name in existing_tables:
                if table_name in Base.metadata.tables:
                    await conn.execute(
                        text(
                            f"SELECT setval('{table_name}_id_seq', COALESCE((SELECT MAX(id) FROM {table_name}), 1), false);"
                        )
                    )

        logger.info("Database migration completed successfully!")
        return True

    except Exception as e:
        logger.error(f"Error migrating database: {e}", exc_info=True)
        return False


if __name__ == "__main__":
    # Setup logging
    from infrastructure.logging import setup_logging

    setup_logging()

    # Run database migration
    success = asyncio.run(migrate_database())
    sys.exit(0 if success else 1)
