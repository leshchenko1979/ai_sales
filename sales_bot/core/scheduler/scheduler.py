"""Task scheduler."""

import asyncio
import logging
from datetime import datetime, time, timedelta

from core.accounts import AccountMonitor
from core.db import AccountQueries, with_queries
from infrastructure.config import CHECK_INTERVAL, RESET_HOUR_UTC

logger = logging.getLogger(__name__)


class Scheduler:
    """Task scheduler."""

    def __init__(self):
        """Initialize scheduler."""
        self.monitor = AccountMonitor()
        self.running = False
        self.tasks = []

    async def start(self):
        """Start scheduler."""
        if self.running:
            return

        self.running = True
        self.tasks = [
            asyncio.create_task(self._check_accounts()),
            asyncio.create_task(self._reset_daily_limits()),
        ]

        logger.info("Scheduler started")

    async def stop(self):
        """Stop scheduler."""
        if not self.running:
            return

        self.running = False
        for task in self.tasks:
            task.cancel()

        await asyncio.gather(*self.tasks, return_exceptions=True)
        logger.info("Scheduler stopped")

    async def _check_accounts(self):
        """Check accounts periodically."""
        while self.running:
            try:
                await self.monitor.check_accounts()
                await asyncio.sleep(CHECK_INTERVAL)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error checking accounts: {e}", exc_info=True)
                await asyncio.sleep(60)  # Wait before retry

    @with_queries(AccountQueries)
    async def _reset_daily_limits(self, queries: AccountQueries):
        """Reset daily message limits at specified hour."""
        while self.running:
            try:
                # Calculate time until next reset
                now = datetime.utcnow()
                reset_time = time(hour=RESET_HOUR_UTC)
                next_reset = datetime.combine(now.date(), reset_time)

                if now.time() >= reset_time:
                    next_reset += timedelta(days=1)

                # Wait until next reset
                wait_seconds = (next_reset - now).total_seconds()
                await asyncio.sleep(wait_seconds)

                # Reset limits
                if await queries.reset_daily_limits():
                    logger.info("Daily limits reset")
                else:
                    logger.warning("Failed to reset daily limits")

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error resetting daily limits: {e}", exc_info=True)
                await asyncio.sleep(60)  # Wait before retry
