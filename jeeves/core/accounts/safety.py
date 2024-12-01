"""Account safety checks."""

import logging
from datetime import datetime, time, timedelta, timezone

from core.db import with_queries
from infrastructure.config import (
    MAX_MESSAGES_PER_DAY,
    MAX_MESSAGES_PER_HOUR,
    MIN_MESSAGE_DELAY,
    RESET_HOUR_UTC,
)

from .models import Account
from .queries.account import AccountQueries

logger = logging.getLogger(__name__)


def get_utc_now() -> datetime:
    """Get current UTC time as naive datetime."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


class AccountSafety:
    """Account safety checks."""

    @staticmethod
    def can_send_message(account: Account) -> bool:
        """Check if account can send message."""
        # Check status
        if not account.can_be_used:
            return False

        # Check daily limit
        if account.daily_messages >= MAX_MESSAGES_PER_DAY:
            logger.warning(
                f"Daily message limit reached for {account.phone}: "
                f"{account.daily_messages}/{MAX_MESSAGES_PER_DAY}"
            )
            return False

        # Check hourly limit
        if account.last_used_at:
            messages_last_hour = 0
            hour_ago = get_utc_now() - timedelta(hours=1)

            if account.last_used_at > hour_ago:
                messages_last_hour = account.daily_messages

            if messages_last_hour >= MAX_MESSAGES_PER_HOUR:
                logger.warning(
                    f"Hourly message limit reached for {account.phone}: "
                    f"{messages_last_hour}/{MAX_MESSAGES_PER_HOUR}"
                )
                return False

            # Check minimum delay
            if (
                get_utc_now() - account.last_used_at
            ).total_seconds() < MIN_MESSAGE_DELAY:
                logger.warning(f"Message delay not passed for {account.phone}")
                return False

        return True

    @staticmethod
    def get_next_reset_time() -> datetime:
        """Get next daily limit reset time."""
        now = get_utc_now()
        reset_time = time(hour=RESET_HOUR_UTC)
        next_reset = datetime.combine(now.date(), reset_time)

        if now.time() >= reset_time:
            next_reset += timedelta(days=1)

        return next_reset

    @with_queries(AccountQueries)
    async def reset_daily_limits(self, queries: AccountQueries) -> bool:
        """Reset daily message limits."""
        try:
            return await queries.reset_daily_limits()
        except Exception as e:
            logger.error(f"Error resetting daily limits: {e}", exc_info=True)
            return False
