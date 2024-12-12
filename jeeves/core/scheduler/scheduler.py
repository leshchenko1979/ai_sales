"""Scheduler module for managing periodic tasks and campaign execution.

This module provides centralized task scheduling for:
1. Account monitoring and safety checks
2. Daily limit resets
3. Campaign management and execution
"""

# Standard library imports
import asyncio
import logging
from datetime import datetime, time, timedelta
from typing import Dict, List

# Local application imports
from core import db
from core.accounts import AccountMonitor
from core.accounts.queries import AccountQueries
from core.campaigns import models as campaign_models
from core.campaigns.queries import CampaignQueries
from core.campaigns.runner import CampaignRunner

# Configuration imports
from infrastructure.config import CHECK_INTERVAL, RESET_HOUR_UTC
from infrastructure.logging import trace

logger = logging.getLogger(__name__)


class SchedulerError(Exception):
    """Base exception for scheduler errors."""


class TaskError(SchedulerError):
    """Error in scheduled task execution."""


class Scheduler:
    """Task scheduler for managing periodic operations.

    This class manages:
    1. Account monitoring and safety checks
    2. Daily message limit resets
    3. Campaign execution and lifecycle

    Attributes:
        monitor: Account monitoring component
        running: Flag indicating if scheduler is running
        tasks: List of running scheduler tasks
        campaign_runners: Dictionary mapping campaign IDs to their runners
    """

    def __init__(self):
        """Initialize scheduler components."""
        self.monitor = AccountMonitor()
        self.running = False
        self.tasks: List[asyncio.Task] = []
        self.campaign_runners: Dict[int, CampaignRunner] = {}

    # Core operations
    @trace
    async def start(self) -> None:
        """Start scheduler and all managed tasks.

        This method:
        1. Starts account monitoring
        2. Initializes daily limit reset task
        3. Begins campaign management

        Raises:
            SchedulerError: If scheduler is already running
        """
        if self.running:
            raise SchedulerError("Scheduler is already running")

        self.running = True
        self.tasks = [
            asyncio.create_task(self._check_accounts()),
            asyncio.create_task(self._reset_daily_limits()),
            asyncio.create_task(self._manage_campaigns()),
        ]

    @trace
    async def stop(self) -> None:
        """Stop scheduler and cleanup all tasks.

        This method ensures:
        1. All campaign runners are stopped
        2. All scheduled tasks are cancelled
        3. Resources are properly cleaned up
        """
        if not self.running:
            return

        self.running = False

        # Stop campaign runners
        await self._stop_campaign_runners()

        # Cancel and cleanup scheduler tasks
        await self._cleanup_tasks()

    # Account operations
    @trace
    async def _check_accounts(self) -> None:
        """Periodically check account status and safety.

        This task:
        1. Monitors account health
        2. Updates account status
        3. Handles safety violations
        """
        while self.running:
            try:
                await self.monitor.check_accounts()
                await asyncio.sleep(CHECK_INTERVAL)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Account check error: {e}", exc_info=True)
                await self._handle_task_error()

    @trace
    @db.decorators.with_queries(AccountQueries)
    async def _reset_daily_limits(self, queries: AccountQueries) -> None:
        """Reset daily message limits at configured UTC hour.

        This task:
        1. Calculates next reset time
        2. Waits until reset time
        3. Resets all account limits
        """
        while self.running:
            try:
                # Calculate next reset time
                next_reset = await self._calculate_next_reset()
                await asyncio.sleep(next_reset)

                # Perform reset
                if await queries.reset_daily_limits():
                    logger.info("Daily limits reset successfully")
                else:
                    logger.warning("Failed to reset daily limits")

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Limit reset error: {e}", exc_info=True)
                await self._handle_task_error()

    # Campaign operations
    @trace
    @db.decorators.with_queries(CampaignQueries)
    async def _manage_campaigns(self, queries: CampaignQueries) -> None:
        """Manage active campaign lifecycle.

        This task:
        1. Monitors active campaigns
        2. Starts new campaign runners
        3. Stops inactive campaign runners
        """
        while self.running:
            try:
                # Get active campaigns and their IDs
                active_campaigns = await queries.get_active_campaigns()
                active_ids = {c.id for c in active_campaigns}

                # Update campaign runners
                await self._stop_inactive_runners(active_ids)
                await self._start_new_runners(active_campaigns)

                await asyncio.sleep(60)  # Check every minute

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Campaign management error: {e}", exc_info=True)
                await self._handle_task_error()

    # Helper methods
    @trace
    async def _calculate_next_reset(self) -> float:
        """Calculate seconds until next daily limit reset.

        Returns:
            Seconds until next reset time
        """
        now = datetime.utcnow()
        reset_time = time(hour=RESET_HOUR_UTC)
        next_reset = datetime.combine(now.date(), reset_time)

        if now.time() >= reset_time:
            next_reset += timedelta(days=1)

        return (next_reset - now).total_seconds()

    @trace
    async def _handle_task_error(self) -> None:
        """Handle task errors with exponential backoff."""
        await asyncio.sleep(60)  # Wait before retry

    @trace
    async def _stop_campaign_runners(self) -> None:
        """Stop all active campaign runners."""
        for runner in self.campaign_runners.values():
            await runner.stop()
        self.campaign_runners.clear()

    @trace
    async def _cleanup_tasks(self) -> None:
        """Cancel and cleanup all scheduler tasks."""
        for task in self.tasks:
            task.cancel()
        await asyncio.gather(*self.tasks, return_exceptions=True)

    @trace
    async def _stop_inactive_runners(self, active_ids: set[int]) -> None:
        """Stop runners for inactive campaigns.

        Args:
            active_ids: Set of active campaign IDs
        """
        for campaign_id in list(self.campaign_runners.keys()):
            if campaign_id not in active_ids:
                await self.campaign_runners[campaign_id].stop()
                del self.campaign_runners[campaign_id]
                logger.info(f"Stopped runner for campaign {campaign_id}")

    @trace
    async def _start_new_runners(
        self, campaigns: List[campaign_models.Campaign]
    ) -> None:
        """Start runners for new active campaigns.

        Args:
            campaigns: List of active campaigns
        """
        for campaign in campaigns:
            if campaign.id not in self.campaign_runners:
                runner = CampaignRunner(campaign.id)
                self.campaign_runners[campaign.id] = runner
                asyncio.create_task(runner.run())
                logger.info(f"Started runner for campaign {campaign.id}")
