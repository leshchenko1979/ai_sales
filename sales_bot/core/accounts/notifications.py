"""Account notifications."""

import logging
from datetime import datetime

from core.db import AccountQueries, with_queries
from infrastructure.config import BOT_TOKEN
from pyrogram import Client

from .models import Account

logger = logging.getLogger(__name__)


class AccountNotifier:
    """Account notifier."""

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
        """Notify about flood wait."""
        try:
            # Update account
            account.flood_wait_until = flood_wait_until
            account.updated_at = datetime.utcnow()
            queries.session.add(account)

            # Send notification
            await self.bot.send_message(
                chat_id=account.id,
                text=f"Account {account.phone} is in flood wait "
                f"until {flood_wait_until}",
            )
            return True

        except Exception as e:
            logger.error(
                f"Error notifying flood wait for {account.phone}: {e}", exc_info=True
            )
            return False

    @with_queries(AccountQueries)
    async def notify_account_blocked(
        self, account: Account, queries: AccountQueries
    ) -> bool:
        """Notify about account block."""
        try:
            # Update account
            account.status = "blocked"
            account.updated_at = datetime.utcnow()
            queries.session.add(account)

            # Send notification
            await self.bot.send_message(
                chat_id=account.id,
                text=f"Account {account.phone} has been blocked",
            )
            return True

        except Exception as e:
            logger.error(
                f"Error notifying account block for {account.phone}: {e}", exc_info=True
            )
            return False
