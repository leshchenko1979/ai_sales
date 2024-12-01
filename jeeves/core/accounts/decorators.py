"""Account client decorators."""

import asyncio
import functools
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Optional, TypeVar, Union

from pyrogram.errors import (
    AuthKeyDuplicated,
    AuthKeyUnregistered,
    FloodWait,
    SessionPasswordNeeded,
    UserDeactivated,
    UserDeactivatedBan,
)

logger = logging.getLogger(__name__)

T = TypeVar("T")
ReturnType = Optional[Union[T, datetime, bool, str, list]]


def require_client(initialized: bool = False) -> Callable:
    """Ensure client is properly initialized.

    Args:
        initialized: If True, also checks _initialized flag
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(self, *args: Any, **kwargs: Any) -> ReturnType:
            if not self.client:
                logger.error(f"Client not initialized for operation: {func.__name__}")
                return_type = func.__annotations__.get("return")
                return False if return_type == bool else None

            if initialized and not self._initialized:
                logger.error(
                    f"Client not fully initialized for operation: {func.__name__}"
                )
                return None

            return await func(self, *args, **kwargs)

        return wrapper

    return decorator


def handle_auth_errors(operation: str) -> Callable:
    """Handle authentication related errors.

    Should be applied to auth operations like sign_in, send_code.
    Handles:
        - SessionPasswordNeeded
        - AuthKeyDuplicated
        - AuthKeyUnregistered
        - UserDeactivated
        - UserDeactivatedBan
    """

    def decorator(func: Callable[..., T]) -> Callable[..., ReturnType]:
        @functools.wraps(func)
        async def wrapper(self, *args: Any, **kwargs: Any) -> ReturnType:
            try:
                return await func(self, *args, **kwargs)
            except SessionPasswordNeeded:
                logger.warning(f"2FA required during {operation}")
                return None
            except (AuthKeyDuplicated, AuthKeyUnregistered) as e:
                logger.warning(f"Auth key error during {operation}: {e}")
                await self.stop()  # Cleanup on auth errors
                return None
            except (UserDeactivated, UserDeactivatedBan) as e:
                logger.error(f"Account deactivated during {operation}: {e}")
                await self.stop()
                return None
            except Exception as e:
                logger.error(f"Error during {operation}: {e}", exc_info=True)
                return None

        return wrapper

    return decorator


def handle_flood_wait(
    operation: str, return_time: bool = False, sleep: bool = False
) -> Callable:
    """Handle Telegram flood wait errors.

    Args:
        operation: Name of the operation for logging
        return_time: If True, returns flood wait end time instead of None
        sleep: If True, sleeps for flood wait duration instead of returning
    """

    def decorator(func: Callable[..., T]) -> Callable[..., ReturnType]:
        @functools.wraps(func)
        async def wrapper(self, *args: Any, **kwargs: Any) -> ReturnType:
            try:
                return await func(self, *args, **kwargs)
            except FloodWait as e:
                logger.warning(f"FloodWait during {operation}: {e.value} seconds")
                if sleep:
                    await asyncio.sleep(e.value)
                    return await func(self, *args, **kwargs)
                if return_time:
                    return datetime.now(timezone.utc) + timedelta(seconds=e.value)
                return None
            except Exception as e:
                logger.error(f"Error during {operation}: {e}", exc_info=True)
                return None

        return wrapper

    return decorator


def log_operation(operation: str) -> Callable:
    """Log operation start and completion.

    Should be the first decorator applied to get accurate timing.
    """

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        async def wrapper(self, *args: Any, **kwargs: Any) -> T:
            start_time = datetime.now()
            logger.debug(f"Starting {operation} for {self.phone}")
            try:
                result = await func(self, *args, **kwargs)
                duration = (datetime.now() - start_time).total_seconds()
                logger.debug(
                    f"Completed {operation} for {self.phone} in {duration:.2f}s"
                )
                return result
            except Exception as e:
                duration = (datetime.now() - start_time).total_seconds()
                logger.error(
                    f"Failed {operation} for {self.phone} after {duration:.2f}s: {e}"
                )
                raise

        return wrapper

    return decorator
