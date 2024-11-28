"""Account monitoring."""

import logging
from datetime import datetime
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
        try:
            # Skip if not active
            if account.status != AccountStatus.active:
                return False

            # Create client
            client = AccountClient(account.phone, account.session_string)
            if not await client.start():
                # Session expired or invalid
                account.status = AccountStatus.disabled
                account.updated_at = datetime.utcnow()
                queries.session.add(account)
                return False

            try:
                # Check flood wait
                flood_wait_until = await client.check_flood_wait()
                if flood_wait_until:
                    account.flood_wait_until = flood_wait_until
                    account.updated_at = datetime.utcnow()
                    queries.session.add(account)
                    return False

                # Update last used time
                account.last_used_at = datetime.utcnow()
                account.updated_at = datetime.utcnow()
                queries.session.add(account)
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
            # Get all accounts
            accounts = await queries.get_all_accounts()
            if not accounts:
                return None

            # Prepare statistics
            stats = {
                "total": len(accounts),
                "active": 0,
                "disabled": 0,
                "blocked": 0,
                "flood_wait": 0,
            }

            # Check each account
            for account in accounts:
                # Update statistics
                stats[account.status.value] += 1
                if account.is_flood_wait:
                    stats["flood_wait"] += 1

                # Skip if not active
                if account.status != AccountStatus.active:
                    continue

                # Check account
                await self.check_account(account)

            return stats

        except Exception as e:
            logger.error(f"Error checking accounts: {e}", exc_info=True)
            return None
