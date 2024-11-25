import logging

from sqlalchemy_utils import create_database, database_exists

from .models import Base
from .queries import engine

logger = logging.getLogger(__name__)


async def create_schema():
    """Создание базы данных и таблиц"""
    logger.info("Creating database schema...")

    # Create database if it doesn't exist
    if not database_exists(engine.url):
        logger.info("Creating database...")
        create_database(engine.url)

    # Create all tables
    logger.info("Creating tables...")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
