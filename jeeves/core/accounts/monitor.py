"""Account monitoring functionality."""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Optional

from .models.account import Account, AccountStatus
from .queries.account import AccountQueries

logger = logging.getLogger(__name__)


class AccountMonitor:
    """Monitors and manages account statuses and limits."""

    def __init__(self, queries: AccountQueries):
        self.queries = queries
        self._running = False
        self._task: Optional[asyncio.Task] = None

    async def start(self):
        """Start the account monitor."""
        if self._running:
            return

        self._running = True
        self._task = asyncio.create_task(self._monitor_loop())
        logger.info("Account monitor started")

    async def stop(self):
        """Stop the account monitor."""
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

    async def _monitor_loop(self):
        """Main monitoring loop."""
        while self._running:
            try:
                await self._check_accounts()
                await asyncio.sleep(300)  # Check every 5 minutes
            except Exception as e:
                logger.error(f"Error in account monitor: {e}")
                await asyncio.sleep(60)  # Wait before retry on error

    async def _check_accounts(self):
        """Check all accounts for issues."""
        accounts = await self.queries.get_all_accounts()

        for account in accounts:
            try:
                await self._check_account(account)
            except Exception as e:
                logger.error(f"Error checking account {account.phone}: {e}")

    async def _check_account(self, account: Account):
        """Check individual account status and limits."""
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
            await self.queries.update_account(account.phone, **updates)
