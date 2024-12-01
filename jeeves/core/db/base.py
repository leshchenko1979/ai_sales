"""Base database components."""

import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from infrastructure.config import DATABASE_URL
from sqlalchemy.exc import SQLAlchemyError
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

    async def _safe_commit(self) -> bool:
        """Safely commit changes."""
        try:
            await self.session.commit()
            return True
        except SQLAlchemyError as e:
            logger.error(f"Failed to commit: {e}")
            await self.session.rollback()
            return False


@asynccontextmanager
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Get database session."""
    async with async_session() as session:
        try:
            yield session
        except Exception as e:
            await session.rollback()
            logger.error(f"Database error: {e}")
            raise
        finally:
            await session.close()
