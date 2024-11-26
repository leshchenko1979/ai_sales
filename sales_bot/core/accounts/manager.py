"""Account manager."""

import logging
from datetime import datetime
from typing import Optional

from core.db import AccountQueries, with_queries

from .client import AccountClient
from .models import Account, AccountStatus

logger = logging.getLogger(__name__)


class AccountManager:
    """Account manager."""

    @with_queries(AccountQueries)
    async def get_or_create_account(
        self, phone: str, queries: AccountQueries
    ) -> Optional[Account]:
        """Get or create account."""
        try:
            # Try to get existing account
            account = await queries.get_account_by_phone(phone)
            if account:
                return account

            # Create new account
            return await queries.create_account(phone)

        except Exception as e:
            logger.error(
                f"Error getting or creating account {phone}: {e}", exc_info=True
            )
            return None

    @with_queries(AccountQueries)
    async def request_code(self, phone: str, queries: AccountQueries) -> bool:
        """Request authorization code."""
        try:
            # Get account
            account = await queries.get_account_by_phone(phone)
            if not account:
                logger.error(f"Account {phone} not found")
                return False

            # Create client
            client = AccountClient(phone)
            if not await client.start():
                return False

            try:
                # Send code
                if not await client.send_code():
                    return False

                # Update account status
                account.status = AccountStatus.code_requested
                account.updated_at = datetime.utcnow()
                queries.session.add(account)
                return True

            finally:
                await client.stop()

        except Exception as e:
            logger.error(f"Error requesting code for {phone}: {e}", exc_info=True)
            return False

    @with_queries(AccountQueries)
    async def authorize_account(
        self, phone: str, code: str, queries: AccountQueries
    ) -> bool:
        """Authorize account with code."""
        try:
            # Get account
            account = await queries.get_account_by_phone(phone)
            if not account:
                logger.error(f"Account {phone} not found")
                return False

            # Create client
            client = AccountClient(phone)
            if not await client.start():
                return False

            try:
                # Sign in
                session_string = await client.sign_in(code)
                if not session_string:
                    return False

                # Update account
                account.session_string = session_string
                account.status = AccountStatus.active
                account.updated_at = datetime.utcnow()
                queries.session.add(account)
                return True

            finally:
                await client.stop()

        except Exception as e:
            logger.error(f"Error authorizing {phone}: {e}", exc_info=True)
            return False

    @with_queries(AccountQueries)
    async def get_available_account(self, queries: AccountQueries) -> Optional[Account]:
        """Get available account for messaging."""
        try:
            # Get active accounts
            accounts = await queries.get_active_accounts()
            if not accounts:
                return None

            # Return first available account
            for account in accounts:
                if account.can_be_used:
                    return account

            return None

        except Exception as e:
            logger.error(f"Error getting available account: {e}", exc_info=True)
            return None
