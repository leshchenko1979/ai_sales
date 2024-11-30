"""Account manager."""

import logging
from datetime import datetime
from typing import Optional

from core.db import with_queries
from utils.phone import normalize_phone

from .client_manager import ClientManager
from .models import Account, AccountStatus
from .queries.account import AccountQueries

logger = logging.getLogger(__name__)


class AccountManager:
    """Account manager."""

    def __init__(self):
        """Initialize manager."""
        self.client_manager = ClientManager()

    @with_queries(AccountQueries)
    async def get_or_create_account(
        self, phone: str, queries: AccountQueries
    ) -> Optional[Account]:
        """Get or create account."""
        try:
            phone = normalize_phone(phone)

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
            phone = normalize_phone(phone)

            # Get account
            account = await queries.get_account_by_phone(phone)
            if not account:
                logger.error(f"Account {phone} not found")
                return False

            # Don't request code for active accounts
            if account.status == AccountStatus.active:
                logger.warning(
                    f"Account {phone} is already active, code request blocked"
                )
                return False

            # Get client
            client = await self.client_manager.get_client(phone)
            if not client:
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
                await self.client_manager.release_client(phone)

        except Exception as e:
            logger.error(f"Error requesting code for {phone}: {e}", exc_info=True)
            await self.client_manager.release_client(phone)
            return False

    @with_queries(AccountQueries)
    async def authorize_account(
        self, phone: str, code: str, queries: AccountQueries
    ) -> bool:
        """Authorize account with code."""
        try:
            phone = normalize_phone(phone)

            # Get account
            account = await queries.get_account_by_phone(phone)
            if not account:
                logger.error(f"Account {phone} not found")
                return False

            # For active accounts, just verify connection
            if account.status == AccountStatus.active:
                client = await self.client_manager.get_client(
                    phone, account.session_string
                )
                success = client is not None
                if client:
                    await self.client_manager.release_client(phone)
                return success

            # Get client (should have phone_code_hash from request_code)
            client = await self.client_manager.get_client(phone)
            if not client:
                logger.error(f"No client found for {phone}")
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
                await self.client_manager.release_client(phone)

        except Exception as e:
            logger.error(f"Error authorizing {phone}: {e}", exc_info=True)
            await self.client_manager.release_client(phone)
            return False

    @with_queries(AccountQueries)
    async def get_available_account(self, queries: AccountQueries) -> Optional[Account]:
        """Get available account for messaging."""
        try:
            # Get active accounts
            accounts = await queries.get_active_accounts()
            if not accounts:
                return None

            return next((account for account in accounts if account.can_be_used), None)

        except Exception as e:
            logger.error(f"Error getting available account: {e}", exc_info=True)
            return None
