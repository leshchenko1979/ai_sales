"""Database decorators."""

import functools
import inspect
import logging
import re
from typing import Any, Awaitable, Callable, Tuple, Type, TypeVar, Union

from .base import BaseQueries, get_db

logger = logging.getLogger(__name__)

Q = TypeVar("Q", bound=BaseQueries)
T = TypeVar("T")

QueryClassArg = Union[Type[Q], Tuple[Type[Q], ...], None]


def _to_snake_case(name: str) -> str:
    """Convert CamelCase to snake_case."""
    pattern = re.compile(r"(?<!^)(?=[A-Z])")
    return pattern.sub("_", name).lower()


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

    Returns:
        Decorated function that handles session management.
    """

    def decorator(func: Callable[..., Awaitable[T]]) -> Callable[..., Awaitable[T]]:
        sig = inspect.signature(func)
        is_method = "self" in sig.parameters

        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> T:
            """Wrapper function that manages database session."""
            session = kwargs.pop("session", None)
            external_session = session is not None

            try:
                if not external_session:
                    async with get_db() as session:
                        if query_class is None:
                            if is_method:
                                result = await func(
                                    args[0], session=session, *args[1:], **kwargs
                                )
                            else:
                                result = await func(session=session, *args, **kwargs)
                        elif isinstance(query_class, tuple):
                            # Create instances of all query classes
                            query_instances = {
                                f"{_to_snake_case(qc.__name__)}": qc(session)
                                for qc in query_class
                            }
                            if is_method:
                                result = await func(
                                    args[0], *args[1:], **query_instances, **kwargs
                                )
                            else:
                                result = await func(*args, **query_instances, **kwargs)
                        else:
                            # Single query class
                            queries = query_class(session)
                            if is_method:
                                result = await func(
                                    args[0], queries=queries, *args[1:], **kwargs
                                )
                            else:
                                result = await func(*args, queries=queries, **kwargs)

                        await session.commit()
                        return result
                else:
                    # Use provided session
                    if query_class is None:
                        if is_method:
                            result = await func(
                                args[0], session=session, *args[1:], **kwargs
                            )
                        else:
                            result = await func(session=session, *args, **kwargs)
                    elif isinstance(query_class, tuple):
                        # Create instances of all query classes
                        query_instances = {
                            f"{_to_snake_case(qc.__name__)}": qc(session)
                            for qc in query_class
                        }
                        if is_method:
                            result = await func(
                                args[0], *args[1:], **query_instances, **kwargs
                            )
                        else:
                            result = await func(*args, **query_instances, **kwargs)
                    else:
                        # Single query class
                        queries = query_class(session)
                        if is_method:
                            result = await func(
                                args[0], queries=queries, *args[1:], **kwargs
                            )
                        else:
                            result = await func(*args, queries=queries, **kwargs)
                    return result

            except Exception as e:
                if not external_session and session:
                    await session.rollback()
                logger.error(f"Database operation failed: {e}", exc_info=True)
                raise

        return wrapper

    # Handle case when decorator is used without parameters
    if callable(query_class) and not isinstance(query_class, type):
        func, query_class = query_class, None
        return decorator(func)

    return decorator
