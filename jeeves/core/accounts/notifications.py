"""Account notifications."""

import logging
from datetime import datetime, timezone

from core.db import with_queries
from infrastructure.config import BOT_TOKEN, LESHCHENKO_CHAT_ID
from pyrogram import Client

from .models import Account, AccountStatus
from .queries.account import AccountQueries

logger = logging.getLogger(__name__)


class AccountNotifier:
    """Account status updates and notifications."""

    def __init__(self):
        """Initialize notifier."""
        self.bot = Client(
            name="notifier",
            api_id=None,
            api_hash=None,
            bot_token=BOT_TOKEN,
            in_memory=True,
        )

    @with_queries(AccountQueries)
    async def notify_flood_wait(
        self, account: Account, flood_wait_until: datetime, queries: AccountQueries
    ) -> bool:
        """Update account flood wait status and notify."""
        try:
            # Ensure flood_wait_until is timezone-aware
            if flood_wait_until.tzinfo is None:
                flood_wait_until = flood_wait_until.replace(tzinfo=timezone.utc)

            await queries.update_account(
                account.phone, flood_wait_until=flood_wait_until
            )

            # Log the event
            logger.info(
                f"Account {account.phone} is in flood wait until {flood_wait_until}"
            )

            # Send notification
            await self.bot.send_message(
                chat_id=LESHCHENKO_CHAT_ID,
                text=f"⚠️ Account {account.phone} is in flood wait "
                f"until {flood_wait_until}",
            )
            return True

        except Exception as e:
            logger.error(
                f"Error handling flood wait for {account.phone}: {e}", exc_info=True
            )
            return False

    @with_queries(AccountQueries)
    async def notify_account_blocked(
        self, account: Account, queries: AccountQueries
    ) -> bool:
        """Update account blocked status and notify."""
        try:
            await queries.update_account(account.phone, status=AccountStatus.blocked)

            # Log the event
            logger.warning(f"Account {account.phone} has been blocked")

            # Send notification
            await self.bot.send_message(
                chat_id=LESHCHENKO_CHAT_ID,
                text=f"🚫 Account {account.phone} has been blocked",
            )
            return True

        except Exception as e:
            logger.error(
                f"Error handling blocked status for {account.phone}: {e}", exc_info=True
            )
            return False
