"""Account warmup functionality."""

import asyncio
import logging
import random
from datetime import datetime, timedelta
from typing import Optional

from core.db import with_queries
from pyrogram.errors import FloodWait

from .client_manager import ClientManager
from .models import Account
from .monitor import AccountMonitor
from .notifications import AccountNotifier
from .queries import AccountQueries

logger = logging.getLogger(__name__)

WARMUP_CHANNELS = [
    "telegram",
    "durov",
    "tginfo",
    "cryptocurrency",
    "bitcoin",
    "trading",
]


class AccountWarmup:
    """Account warmup manager.

    This component:
    1. Warms up inactive accounts
    2. Subscribes to channels
    3. Reads messages
    4. Monitors flood wait limits
    """

    def __init__(self):
        """Initialize warmup manager."""
        self.notifier = AccountNotifier()
        self.monitor = AccountMonitor()
        self.client_manager = ClientManager()

    @with_queries(AccountQueries)
    async def warmup_accounts(self, queries: AccountQueries) -> Optional[dict]:
        """Warm up all active accounts.

        Args:
            queries: Database queries executor

        Returns:
            Statistics dictionary if successful, None on error
        """
        try:
            # Get active accounts
            accounts = await queries.get_active_accounts()
            stats = {"total": len(accounts), "success": 0, "failed": 0, "flood_wait": 0}

            # Process each account
            for account in accounts:
                try:
                    # Check account status and availability
                    if not await self.monitor.check_account(account):
                        stats["flood_wait"] += 1
                        continue

                    # Warm up account
                    if await self._warmup_account(queries, account):
                        stats["success"] += 1
                    else:
                        stats["failed"] += 1

                except Exception as e:
                    logger.error(
                        f"Error warming up account {account.phone}: {e}", exc_info=True
                    )
                    stats["failed"] += 1

            # Send report
            await self.notifier.notify_warmup_report(stats)
            return stats

        except Exception as e:
            logger.error(f"Error warming up accounts: {e}", exc_info=True)
            return None

    @with_queries(AccountQueries)
    async def _warmup_account(self, queries: AccountQueries, account: Account) -> bool:
        """Warm up specific account.

        Args:
            queries: Database queries executor
            account: Account to warm up

        Returns:
            True if warmup successful, False otherwise
        """
        try:
            # Get client from manager
            client = await self.client_manager.get_client(
                account.phone, account.session_string
            )
            if not client:
                logger.error(f"Failed to get client for {account.phone}")
                return False

            try:
                # Select random channels
                channels = random.sample(WARMUP_CHANNELS, 3)

                # Subscribe and read messages
                for channel in channels:
                    try:
                        # Join channel
                        await client.join_channel(channel)
                        await asyncio.sleep(random.randint(30, 60))

                        # Read messages
                        await client.read_channel_messages(channel)
                        await asyncio.sleep(random.randint(60, 120))

                    except FloodWait as e:
                        logger.warning(
                            f"FloodWait for {account.phone}: {e.value} seconds"
                        )
                        flood_wait_until = datetime.utcnow() + timedelta(
                            seconds=e.value
                        )
                        await queries.update_account(
                            account.phone, flood_wait_until=flood_wait_until
                        )
                        return False

                    except Exception as e:
                        logger.error(f"Error in channel {channel}: {e}", exc_info=True)
                        continue

                # Update last used timestamp
                await queries.update_account(
                    account.phone, last_used_at=datetime.utcnow()
                )
                return True

            finally:
                # Release client back to manager
                await self.client_manager.release_client(account.phone, queries)

        except Exception as e:
            logger.error(
                f"Error warming up account {account.phone}: {e}", exc_info=True
            )
            return False
