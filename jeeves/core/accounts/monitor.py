"""Account monitoring and safety functionality.

This module provides centralized account monitoring including:
1. Account status checks
2. Safety limits monitoring
3. Usage statistics tracking
"""

# Standard library imports
import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, Optional

# Local application imports
from core import db
from core.accounts.client import AccountClient
from core.accounts.models import Account, AccountStatus
from core.accounts.queries import AccountQueries
from infrastructure.config import (
    MAX_MESSAGES_PER_DAY,
    MAX_MESSAGES_PER_HOUR,
    MIN_MESSAGE_DELAY,
)

logger = logging.getLogger(__name__)


class AccountMonitorError(Exception):
    """Base exception for account monitoring errors."""


class AccountMonitor:
    """Monitors and manages account statuses, safety limits and health.

    This class provides:
    1. Account status monitoring
    2. Safety limit checks and enforcement
    3. Usage statistics collection
    4. Automatic daily limit resets

    Attributes:
        _running: Flag indicating if monitor is running
        _task: Background monitoring task
    """

    def __init__(self):
        """Initialize account monitor."""
        self._running = False
        self._task: Optional[asyncio.Task] = None

    # Core operations
    async def start(self) -> None:
        """Start the account monitor.

        Raises:
            AccountMonitorError: If monitor is already running
        """
        if self._running:
            raise AccountMonitorError("Monitor is already running")

        self._running = True
        self._task = asyncio.create_task(self._monitor_loop())
        logger.info("Account monitor started")

    async def stop(self) -> None:
        """Stop the account monitor gracefully."""
        if not self._running:
            return

        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("Account monitor stopped")

    # Account checks
    @db.decorators.with_queries(AccountQueries)
    async def check_account(self, account: Account, queries: AccountQueries) -> bool:
        """Check individual account status and health.

        Args:
            account: Account to check
            queries: Account queries instance

        Returns:
            True if account is healthy and available, False otherwise
        """
        if account.status != AccountStatus.active:
            return False

        try:
            # Check client connection
            client = AccountClient(account.phone, account.session_string)
            if not await client.start():
                await queries.update_account(
                    account.phone, status=AccountStatus.disabled
                )
                return False

            try:
                # Check flood wait
                flood_wait_until = await client.check_flood_wait()
                if flood_wait_until:
                    if flood_wait_until.tzinfo is None:
                        flood_wait_until = flood_wait_until.replace(tzinfo=timezone.utc)
                    await queries.update_account(
                        account.phone, flood_wait_until=flood_wait_until
                    )
                    return False

                # Update last used timestamp
                await queries.update_account(
                    account.phone, last_used_at=datetime.now(timezone.utc)
                )
                return True

            finally:
                await client.stop()

        except Exception as e:
            logger.error(f"Error checking account {account.phone}: {e}", exc_info=True)
            return False

    @db.decorators.with_queries(AccountQueries)
    async def check_accounts(self, queries: AccountQueries) -> Optional[Dict]:
        """Check all accounts and collect statistics.

        Returns:
            Dictionary with account statistics if successful, None on error
        """
        try:
            accounts = await queries.get_all_accounts()
            if not accounts:
                return None

            stats = {
                "total": len(accounts),
                "new": 0,
                "code_requested": 0,
                "password_requested": 0,
                "active": 0,
                "disabled": 0,
                "blocked": 0,
                "warming": 0,
                "flood_wait": 0,
            }

            for account in accounts:
                stats[account.status.value] += 1
                if account.is_in_flood_wait:
                    stats["flood_wait"] += 1

                if account.status == AccountStatus.active:
                    await self.check_account(account)

            return stats

        except Exception as e:
            logger.error(f"Error checking accounts: {e}", exc_info=True)
            return None

    # Safety checks
    def can_send_message(self, account: Account) -> bool:
        """Check if account can safely send a message.

        Args:
            account: Account to check

        Returns:
            True if account can send message, False otherwise
        """
        # Check status and availability
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
            hour_ago = datetime.now(timezone.utc) - timedelta(hours=1)

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
                datetime.now(timezone.utc) - account.last_used_at
            ).total_seconds() < MIN_MESSAGE_DELAY:
                logger.warning(f"Message delay not passed for {account.phone}")
                return False

        return True

    @db.decorators.with_queries(AccountQueries)
    async def reset_daily_limits(self, queries: AccountQueries) -> bool:
        """Reset daily message limits for all accounts.

        Returns:
            True if reset successful, False otherwise
        """
        try:
            return await queries.reset_daily_limits()
        except Exception as e:
            logger.error(f"Error resetting daily limits: {e}", exc_info=True)
            return False

    # Helper methods
    async def _monitor_loop(self) -> None:
        """Main monitoring loop."""
        while self._running:
            try:
                await self._check_accounts()
                await asyncio.sleep(300)  # Check every 5 minutes
            except Exception as e:
                logger.error(f"Error in monitor loop: {e}")
                await asyncio.sleep(60)  # Wait before retry

    async def _check_accounts(self) -> None:
        """Check all accounts for issues."""
        accounts = await self.check_accounts()
        if not accounts:
            return

        for account in accounts:
            try:
                await self._check_account_limits(account)
            except Exception as e:
                logger.error(f"Error checking account {account.phone}: {e}")

    async def _check_account_limits(self, account: Account) -> None:
        """Check and update account limits.

        Args:
            account: Account to check
        """
        updates = {}

        # Reset daily message count at midnight
        if (
            account.last_reset_at
            and (datetime.utcnow() - account.last_reset_at).days >= 1
        ):
            updates.update({"daily_messages": 0, "last_reset_at": datetime.utcnow()})

        # Check for inactive accounts
        if (
            account.status == AccountStatus.active
            and account.last_used_at
            and datetime.utcnow() - account.last_used_at > timedelta(days=7)
        ):
            updates["status"] = AccountStatus.inactive
            logger.warning(
                f"Account {account.phone} marked as inactive due to inactivity"
            )

        if updates:
            await self._update_account(account.phone, updates)
