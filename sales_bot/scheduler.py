import asyncio
import logging
from datetime import datetime, time, timedelta
from typing import Optional

from accounts.monitoring import AccountMonitor
from accounts.notifications import AccountNotifier
from accounts.rotation import AccountRotator
from accounts.warmup import AccountWarmup
from db.queries import AccountQueries, get_db

logger = logging.getLogger(__name__)


class AccountScheduler:
    def __init__(self):
        self.monitor: Optional[AccountMonitor] = None
        self.notifier: Optional[AccountNotifier] = None
        self.rotator: Optional[AccountRotator] = None
        self.warmup: Optional[AccountWarmup] = None
        self._running = False
        self._tasks = []

    async def start(self):
        """Start scheduler"""
        if self._running:
            return

        # Initialize components
        async with get_db() as db:
            self.monitor = AccountMonitor(db)
            self.rotator = AccountRotator(db)
            self.warmup = AccountWarmup(db)

        self._running = True

        # Schedule tasks
        self._tasks = [
            asyncio.create_task(self._run_periodic_check()),
            asyncio.create_task(self._run_daily_reset()),
            asyncio.create_task(self._run_account_rotation()),
            asyncio.create_task(self._run_account_warmup()),
        ]

        logger.info("Account scheduler started")

    async def stop(self):
        """Stop scheduler"""
        self._running = False

        # Cancel all tasks
        for task in self._tasks:
            task.cancel()

        # Wait for tasks to complete
        await asyncio.gather(*self._tasks, return_exceptions=True)

        # Cleanup
        self._tasks = []
        logger.info("Account scheduler stopped")

    async def _run_periodic_check(self):
        """Run periodic account checks"""
        CHECK_INTERVAL = 3600  # 1 hour in seconds

        while self._running:
            try:
                logger.info("Starting periodic account check")
                stats = await self.monitor.check_all_accounts()
                logger.info(f"Account check completed: {stats}")

                await asyncio.sleep(CHECK_INTERVAL)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in periodic check: {e}")
                await asyncio.sleep(60)  # Wait a bit before retry

    async def _run_daily_reset(self):
        """Run daily message counter reset"""
        while self._running:
            try:
                # Calculate time until next reset (3:00 AM)
                now = datetime.now()
                reset_time = time(hour=3, minute=0)

                next_reset = datetime.combine(
                    (
                        now.date()
                        if now.time() < reset_time
                        else now.date() + timedelta(days=1)
                    ),
                    reset_time,
                )

                # Sleep until next reset
                sleep_seconds = (next_reset - now).total_seconds()
                await asyncio.sleep(sleep_seconds)

                # Reset counters
                logger.info("Starting daily message counter reset")
                async with get_db() as db:
                    account_queries = AccountQueries(db)
                    await account_queries.reset_daily_messages()
                    logger.info("Daily message counters reset completed")

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in daily reset: {e}")
                await asyncio.sleep(60)  # Wait a bit before retry

    async def _run_account_rotation(self):
        """Run periodic account rotation"""
        ROTATION_INTERVAL = 1800  # 30 minutes

        while self._running:
            try:
                logger.info("Starting account rotation")
                stats = await self.rotator.rotate_accounts()
                logger.info(f"Account rotation completed: {stats}")

                await asyncio.sleep(ROTATION_INTERVAL)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in account rotation: {e}")
                await asyncio.sleep(60)  # Wait a bit before retry

    async def _run_account_warmup(self):
        """Run periodic account warmup"""
        WARMUP_INTERVAL = 7200  # 2 hours

        while self._running:
            try:
                logger.info("Starting account warmup")
                stats = await self.warmup.warmup_new_accounts()
                logger.info(f"Account warmup completed: {stats}")

                await asyncio.sleep(WARMUP_INTERVAL)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in account warmup: {e}")
                await asyncio.sleep(60)  # Wait a bit before retry

    async def reset_daily_limits(self):
        """Reset daily message limits for all accounts"""
        try:
            async with get_db() as db:
                account_queries = AccountQueries(db)
                await account_queries.reset_daily_messages()
                logger.info("Daily message limits reset")
        except Exception as e:
            logger.error(f"Failed to reset daily limits: {e}")

    async def perform_warmup(self):
        """Perform account warmup"""
        try:
            async with get_db() as db:
                account_queries = AccountQueries(db)
                await account_queries.get_accounts_for_warmup()
                # Rest of warmup logic...
        except Exception as e:
            logger.error(f"Failed to perform warmup: {e}")
