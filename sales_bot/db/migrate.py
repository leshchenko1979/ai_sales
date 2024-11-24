import asyncio
import logging
from pathlib import Path
from sqlalchemy.ext.asyncio import create_async_engine
from config import DATABASE_URL

logger = logging.getLogger(__name__)

async def apply_migration():
    """Apply database migration"""
    try:
        # Read migration file
        migration_path = Path(__file__).parent / 'init_db.sql'
        with open(migration_path, 'r') as f:
            migration_sql = f.read()

        # Create async engine
        engine = create_async_engine(DATABASE_URL)

        # Apply migration
        async with engine.begin() as conn:
            # Split migration into separate statements
            statements = migration_sql.split(';')

            for statement in statements:
                if statement.strip():
                    await conn.execute(statement)

        logger.info("Migration completed successfully")

    except Exception as e:
        logger.error(f"Error applying migration: {e}")
        raise

def main():
    """Main entry point for migration script"""
    try:
        asyncio.run(apply_migration())
    except KeyboardInterrupt:
        logger.info("Migration interrupted by user")
    except Exception as e:
        logger.error(f"Migration failed: {e}")
        exit(1)

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    main()
