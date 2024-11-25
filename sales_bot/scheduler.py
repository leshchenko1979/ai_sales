import asyncio
import logging
from typing import Optional

from accounts.monitoring import AccountMonitor
from accounts.notifications import AccountNotifier
from accounts.rotation import AccountRotation
from accounts.warmup import AccountWarmup
from db.queries import AccountQueries, get_db
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


class AccountScheduler:
    def __init__(self):
        self.monitor: Optional[AccountMonitor] = None
        self.notifier: Optional[AccountNotifier] = None
        self.rotator: Optional[AccountRotation] = None
        self.warmup: Optional[AccountWarmup] = None
        self.db_session: Optional[AsyncSession] = None
        self._running = False
        self._tasks = []

    async def start(self):
        """Start scheduler"""
        if self._running:
            return

        # Get database session
        async with get_db() as session:
            self.db_session = session
            queries = AccountQueries(session)

            # Initialize components
            self.notifier = AccountNotifier()
            self.monitor = AccountMonitor(queries, self.notifier)
            self.rotator = AccountRotation(queries, self.notifier)
            self.warmup = AccountWarmup(queries, self.notifier)

            self._running = True

            # Schedule tasks
            self._tasks = [
                asyncio.create_task(self._run_account_monitor()),
                asyncio.create_task(self._run_account_rotation()),
                asyncio.create_task(self._run_account_warmup()),
            ]

        logger.info("Account scheduler started")

    async def stop(self):
        """Stop scheduler"""
        if not self._running:
            return

        # Cancel all tasks
        for task in self._tasks:
            task.cancel()

        # Wait for tasks to complete
        await asyncio.gather(*self._tasks, return_exceptions=True)
        self._tasks.clear()

        # Close database session
        if self.db_session:
            await self.db_session.close()
            self.db_session = None

        self._running = False
        logger.info("Account scheduler stopped")

    async def _run_account_monitor(self):
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
                logger.error(f"Error in periodic check: {e}", exc_info=True)
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
                logger.error(f"Error in account rotation: {e}", exc_info=True)
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
                logger.error(f"Error in account warmup: {e}", exc_info=True)
                await asyncio.sleep(60)  # Wait a bit before retry

    async def reset_daily_limits(self):
        """Reset daily message limits for all accounts"""
        try:
            async with self.db_session.begin():
                await self.db_session.execute(
                    "UPDATE accounts SET daily_message_limit = 0"
                )
            logger.info("Daily message limits reset")
        except Exception as e:
            logger.error(f"Failed to reset daily limits: {e}", exc_info=True)

    async def perform_warmup(self):
        """Perform account warmup"""
        try:
            async with self.db_session.begin():
                # Rest of warmup logic...
                pass
        except Exception as e:
            logger.error(f"Failed to perform warmup: {e}", exc_info=True)
