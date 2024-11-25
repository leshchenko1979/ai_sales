import logging

from db.queries import AccountQueries, get_db
from pyrogram.errors import (
    AuthKeyUnregistered,
    SessionRevoked,
    UserDeactivated,
    UserDeactivatedBan,
)

from .client import AccountClient
from .models import Account, AccountStatus
from .notifications import AccountNotifier

logger = logging.getLogger(__name__)


class AccountMonitor:
    def __init__(self, db_session):
        self.db = db_session
        self.queries = AccountQueries(db_session)
        self._error_counts = {}  # account_id -> error_count
        self.notifier = AccountNotifier()

    async def check_account(self, account: Account) -> bool:
        """
        Check if account is working
        Returns True if account is operational
        """
        client = None
        try:
            client = AccountClient(account)
            if not await client.connect():
                return False

            # Try to get account info
            me = await client.client.get_me()
            if not me:
                return False

            # Reset error counter
            self._error_counts.pop(account.id, None)
            return True

        except (
            UserDeactivated,
            SessionRevoked,
            AuthKeyUnregistered,
            UserDeactivatedBan,
        ) as e:
            # Clear signs of blocking
            logger.error(f"Account {account.phone} is blocked: {e}")
            await self._mark_account_blocked(account.id, str(e))
            return False

        except Exception as e:
            # Count other errors
            error_count = self._error_counts.get(account.id, 0) + 1
            self._error_counts[account.id] = error_count

            logger.warning(f"Error checking account {account.phone}: {e}")

            if error_count >= 3:
                await self._mark_account_disabled(
                    account.id, f"3 consecutive errors: {e}"
                )
                return False

            return False

        finally:
            if client:
                await client.disconnect()

    async def check_all_accounts(self) -> dict:
        """
        Check all active accounts
        Returns check statistics
        """
        stats = {"total": 0, "active": 0, "disabled": 0, "blocked": 0}

        try:
            async with get_db() as session:
                queries = AccountQueries(session)
                accounts = await queries.get_active_accounts()
                stats["total"] = len(accounts)

                for account in accounts:
                    try:
                        if await self.check_account(account):
                            stats["active"] += 1
                        elif account.status == AccountStatus.blocked:
                            stats["blocked"] += 1
                        else:
                            stats["disabled"] += 1
                    except Exception as e:
                        logger.error(f"Error checking account {account.phone}: {e}")
                        stats["disabled"] += 1
                        continue

                # Send report
                await self.notifier.notify_status_report(stats)
                return stats

        except Exception as e:
            logger.error(f"Error in check_all_accounts: {e}", exc_info=True)
            return stats

    async def _mark_account_blocked(self, account_id: int, reason: str):
        """Mark account as blocked"""
        async with get_db() as session:
            queries = AccountQueries(session)
            account = await queries.get_account_by_id(account_id)
            if account:
                await queries.update_account_status_by_id(
                    account_id, AccountStatus.blocked
                )
                await self.notifier.notify_blocked(account, reason)
                self._error_counts.pop(account_id, None)

    async def _mark_account_disabled(self, account_id: int, reason: str):
        """Mark account as disabled"""
        async with get_db() as session:
            queries = AccountQueries(session)
            account = await queries.get_account_by_id(account_id)
            if account:
                await queries.update_account_status_by_id(
                    account_id, AccountStatus.disabled
                )
                await self.notifier.notify_disabled(account, reason)
                self._error_counts.pop(account_id, None)
