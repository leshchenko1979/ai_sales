"""Database decorators."""

import functools
import inspect
import logging
import re
from typing import Any, Awaitable, Callable, Optional, Tuple, Type, TypeVar, Union

from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from .base import BaseQueries, get_db

logger = logging.getLogger(__name__)

Q = TypeVar("Q", bound=BaseQueries)
T = TypeVar("T")

QueryClassArg = Union[Type[Q], Tuple[Type[Q], ...], None]


def with_queries(
    query_class: QueryClassArg = None,
) -> Callable[[Callable[..., Awaitable[T]]], Callable[..., Awaitable[T]]]:
    """
    Decorator for business objects that automatically manages database sessions.
    Creates a new session and query object for each method call.

    Args:
        query_class: Optional query class or tuple of query classes to instantiate.
                    If None, raw session is passed.

    Examples:
        @with_queries  # Pass raw session
        async def func(self, session: AsyncSession): ...

        @with_queries(UserQueries)  # Pass single query class
        async def func(self, queries: UserQueries): ...

        @with_queries((UserQueries, PostQueries))  # Pass multiple query classes
        async def func(self, user_queries: UserQueries, post_queries: PostQueries): ...
    """

    def decorator(func: Callable[..., Awaitable[T]]) -> Callable[..., Awaitable[T]]:
        is_method = "self" in inspect.signature(func).parameters

        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> T:
            session = kwargs.pop("session", None)
            external_session = session is not None

            try:
                if not external_session:
                    async with get_db() as session:
                        result = await _execute_with_session(
                            func, session, args, kwargs, query_class, is_method
                        )
                        await session.commit()
                        return result
                else:
                    return await _execute_with_session(
                        func, session, args, kwargs, query_class, is_method
                    )

            except Exception as e:
                if not external_session and session:
                    await session.rollback()
                logger.error(f"Database operation failed: {e}", exc_info=True)
                raise

        return wrapper

    if callable(query_class) and not isinstance(query_class, type):
        func, query_class = query_class, None
        return decorator(func)

    return decorator


def handle_sql_error(operation: str) -> Callable:
    """Decorator for handling SQL errors in query methods."""

    def decorator(func: Callable[..., T]) -> Callable[..., Optional[T]]:
        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Optional[T]:
            try:
                return await func(*args, **kwargs)
            except IntegrityError as e:
                logger.error(f"Integrity error during {operation}: {e}")
                if hasattr(args[0], "session"):
                    await args[0].session.rollback()
                return None
            except SQLAlchemyError as e:
                logger.error(f"Database error during {operation}: {e}")
                if hasattr(args[0], "session"):
                    await args[0].session.rollback()
                return None

        return wrapper

    return decorator


def _to_snake_case(name: str) -> str:
    """Convert CamelCase to snake_case."""
    pattern = re.compile(r"(?<!^)(?=[A-Z])")
    return pattern.sub("_", name).lower()


async def _execute_with_session(
    func: Callable[..., Awaitable[T]],
    session: Any,
    args: Tuple[Any, ...],
    kwargs: dict,
    query_classes: Optional[Union[Type[Q], Tuple[Type[Q], ...]]] = None,
    is_method: bool = False,
) -> T:
    """Execute function with session management."""
    if query_classes is None:
        # Pass raw session
        if is_method:
            return await func(args[0], session=session, *args[1:], **kwargs)
        return await func(session=session, *args, **kwargs)

    if isinstance(query_classes, tuple):
        # Create instances of all query classes
        query_instances = {
            f"{_to_snake_case(qc.__name__)}": qc(session) for qc in query_classes
        }
        if is_method:
            return await func(args[0], *args[1:], **query_instances, **kwargs)
        return await func(*args, **query_instances, **kwargs)

    # Single query class
    queries = query_classes(session)
    if is_method:
        return await func(args[0], queries=queries, *args[1:], **kwargs)
    return await func(*args, queries=queries, **kwargs)
