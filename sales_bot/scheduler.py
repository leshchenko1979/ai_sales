import asyncio
import logging
from datetime import datetime, timedelta
from typing import List

from accounts.monitoring import AccountMonitor
from accounts.notifications import AccountNotifier
from accounts.rotation import AccountRotation
from accounts.safety import AccountSafety
from accounts.warmup import AccountWarmup

logger = logging.getLogger(__name__)

RESET_HOUR_UTC = 0  # Replace with the desired reset hour in UTC


class AccountScheduler:
    def __init__(self):
        """Initialize scheduler components"""
        self.notifier = AccountNotifier()
        self.monitor = AccountMonitor()
        self.rotator = AccountRotation()
        self.warmup = AccountWarmup()
        self.safety = AccountSafety()
        self._running = False
        self._tasks: List[asyncio.Task] = []

    async def start(self):
        """Start scheduler"""
        if self._running:
            return

        self._running = True

        # Schedule tasks
        self._tasks = [
            asyncio.create_task(self._run_account_monitor()),
            asyncio.create_task(self._run_account_rotation()),
            asyncio.create_task(self._run_account_warmup()),
            asyncio.create_task(self._run_daily_reset()),
        ]

        logger.info("Account scheduler started")

    async def stop(self):
        """Stop scheduler"""
        if not self._running:
            return

        self._running = False

        # Cancel tasks
        for task in self._tasks:
            task.cancel()

        # Wait for tasks to complete
        await asyncio.gather(*self._tasks, return_exceptions=True)
        self._tasks.clear()

        logger.info("Account scheduler stopped")

    async def _run_account_monitor(self):
        """Run account monitoring task"""
        while self._running:
            try:
                logger.info("Starting periodic account check")
                stats = await self.monitor.check_all_accounts()
                logger.info(f"Account check completed: {stats}")

                await asyncio.sleep(3600)  # 1 hour

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in periodic check: {e}", exc_info=True)
                await asyncio.sleep(60)  # Wait a bit before retry

    async def _run_account_rotation(self):
        """Run account rotation task"""
        while self._running:
            try:
                logger.info("Starting account rotation")
                stats = await self.rotator.rotate_accounts()
                logger.info(f"Account rotation completed: {stats}")

                await asyncio.sleep(1800)  # 30 minutes

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in account rotation: {e}", exc_info=True)
                await asyncio.sleep(60)  # Wait a bit before retry

    async def _run_account_warmup(self):
        """Run account warmup task"""
        while self._running:
            try:
                logger.info("Starting account warmup")
                stats = await self.warmup.warmup_accounts()
                logger.info(f"Account warmup completed: {stats}")

                await asyncio.sleep(7200)  # 2 hours

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in account warmup: {e}", exc_info=True)
                await asyncio.sleep(60)  # Wait a bit before retry

    async def _run_daily_reset(self):
        """Run daily limit reset task"""
        while self._running:
            try:
                logger.info("Resetting daily message limits")
                await self.safety.reset_daily_limits()

                # Wait until next reset time
                now = datetime.utcnow()
                next_reset = now.replace(
                    hour=RESET_HOUR_UTC, minute=0, second=0, microsecond=0
                )
                if now.hour >= RESET_HOUR_UTC:
                    next_reset += timedelta(days=1)

                sleep_seconds = (next_reset - now).total_seconds()
                await asyncio.sleep(sleep_seconds)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in daily limit reset: {e}", exc_info=True)
                await asyncio.sleep(60)  # Wait a bit before retry
