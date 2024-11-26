"""Database connection and base queries."""

import functools
import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Callable, Optional, TypeVar

from infrastructure.config import DATABASE_URL
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

logger = logging.getLogger(__name__)

# Create engine
engine = create_async_engine(DATABASE_URL)
async_session = async_sessionmaker(engine, expire_on_commit=False)


@asynccontextmanager
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Get database session."""
    session = async_session()
    try:
        yield session
        await session.commit()
    except Exception as e:
        await session.rollback()
        logger.error(f"Database error: {e}", exc_info=True)
        raise
    finally:
        await session.close()


T = TypeVar("T")


def with_queries(queries_class: T) -> Callable:
    """Decorator for using queries in functions."""

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs) -> Optional[T]:
            async with get_db() as session:
                queries = queries_class(session)
                return await func(*args, queries=queries, **kwargs)

        return wrapper

    return decorator


class BaseQueries:
    """Base class for database queries."""

    def __init__(self, session: AsyncSession):
        """Initialize queries."""
        self.session = session
