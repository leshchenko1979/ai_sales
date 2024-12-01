"""Account monitoring."""

import logging
from datetime import datetime, timezone
from typing import Dict, Optional

from core.db import with_queries

from .client import AccountClient
from .models import Account, AccountStatus
from .queries.account import AccountQueries

logger = logging.getLogger(__name__)


class AccountMonitor:
    """Account monitor."""

    @with_queries(AccountQueries)
    async def check_account(self, account: Account, queries: AccountQueries) -> bool:
        """Check account status."""
        if account.status != AccountStatus.active:
            return False

        try:
            client = AccountClient(account.phone, account.session_string)
            if not await client.start():
                await queries.update_account(
                    account.phone, status=AccountStatus.disabled
                )
                return False

            try:
                flood_wait_until = await client.check_flood_wait()
                if flood_wait_until:
                    if flood_wait_until.tzinfo is None:
                        flood_wait_until = flood_wait_until.replace(tzinfo=timezone.utc)
                    await queries.update_account(
                        account.phone, flood_wait_until=flood_wait_until
                    )
                    return False

                await queries.update_account(
                    account.phone, last_used_at=datetime.now(timezone.utc)
                )
                return True

            finally:
                await client.stop()

        except Exception as e:
            logger.error(f"Error checking account {account.phone}: {e}", exc_info=True)
            return False

    @with_queries(AccountQueries)
    async def check_accounts(self, queries: AccountQueries) -> Optional[Dict]:
        """Check all accounts."""
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
