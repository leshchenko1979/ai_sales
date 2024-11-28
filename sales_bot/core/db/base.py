"""Base database module."""

import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from infrastructure.config import DATABASE_URL
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

logger = logging.getLogger(__name__)

# Create async engine
engine = create_async_engine(DATABASE_URL)

# Create async session factory
async_session = sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class BaseQueries:
    """Base class for database queries."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialize base queries."""
        self.session = session


@asynccontextmanager
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Get database session."""
    async with async_session() as session:
        try:
            yield session
            await session.commit()
        except Exception as e:
            await session.rollback()
            logger.error(f"Database error: {e}")
            raise
        finally:
            await session.close()
