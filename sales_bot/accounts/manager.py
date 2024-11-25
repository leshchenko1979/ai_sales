import logging
from typing import Optional

from db.models import AccountStatus
from db.queries import AccountQueries, with_queries

from .client import AccountClient
from .client_manager import AccountClientManager
from .models import Account
from .safety import AccountSafety

logger = logging.getLogger(__name__)


class AccountManager:
    """
    Manages Telegram account operations.
    Maintains active clients and safety rules.
    """

    def __init__(self):
        """Initialize manager with safety rules and client manager"""
        self.safety = AccountSafety()
        self._client_manager = None  # Will be initialized on first use

    async def _get_client_manager(self) -> AccountClientManager:
        """Get singleton instance of client manager"""
        if self._client_manager is None:
            self._client_manager = await AccountClientManager.get_instance()
        return self._client_manager

    @staticmethod
    def _normalize_phone(phone: str) -> str:
        """Normalize phone number to standard format"""
        return (
            phone.strip()
            .replace("+", "")
            .replace(" ", "")
            .replace("-", "")
            .replace("(", "")
            .replace(")", "")
        )

    @with_queries(AccountQueries)
    async def add_account(self, queries: AccountQueries, phone_number: str) -> Account:
        """
        Add new account to database.

        :param queries: Database queries executor
        :param phone_number: Phone number for the account
        :return: Created account
        :raises ValueError: If account with this phone already exists
        """
        try:
            return await queries.create_account(phone_number)
        except Exception as e:
            logger.error(f"Error adding account: {e}", exc_info=True)
            raise

    @with_queries(AccountQueries)
    async def get_or_create_account(
        self, queries: AccountQueries, phone: str
    ) -> Account:
        """
        Get existing account by phone number or create a new one if it doesn't exist.

        :param queries: Database queries executor
        :param phone: Phone number for the account
        :return: Existing or newly created account
        """
        phone = self._normalize_phone(phone)
        try:
            account = await queries.get_account_by_phone(phone)
            if not account:
                account = await queries.create_account(phone)
                logger.info(f"Created new account for phone {phone}")
            return account
        except Exception as e:
            logger.error(f"Error getting or creating account: {e}", exc_info=True)
            raise

    async def get_client(self, account: Account) -> Optional[AccountClient]:
        """
        Get client for the account. Creates new client if needed.

        :param account: Account to get client for
        :return: AccountClient instance or None if creation failed
        """
        if account.status == AccountStatus.disabled:
            logger.error(f"Cannot get client for disabled account {account.id}")
            return None

        client_manager = await self._get_client_manager()
        return await client_manager.get_client(account)

    @with_queries(AccountQueries)
    async def get_available_account(self, queries: AccountQueries) -> Optional[Account]:
        """
        Get account available for sending messages.

        :param queries: Database queries executor
        :return: Available account or None
        """
        try:
            accounts = await queries.get_active_accounts()
            for account in accounts:
                if account.can_be_used and self.safety.can_send_message(account):
                    return account
            return None
        except Exception as e:
            logger.error(f"Failed to get available account: {e}", exc_info=True)
            return None

    @with_queries(AccountQueries)
    async def send_message(
        self, queries: AccountQueries, account: Account, username: str, text: str
    ) -> bool:
        """
        Send message using specified account.

        :param queries: Database queries executor
        :param account: Account to send from
        :param username: Target username
        :param text: Message text
        :return: True if message sent successfully
        """
        try:
            if not account.can_be_used:
                logger.error(
                    f"Account {account.phone} is not available for sending messages"
                )
                return False

            # Check safety
            if not self.safety.can_send_message(account):
                return False

            # Get client through manager
            client = await self.get_client(account)
            if not client:
                return False

            # Send message
            success = await client.send_message(username, text)
            if success:
                # Safety update
                self.safety.record_message(account)
                # Update message count in database
                await queries.increment_messages(account.id)

            return success

        except Exception as e:
            logger.error(
                f"Failed to send message from {account.phone}: {e}", exc_info=True
            )
            return False

    @with_queries(AccountQueries)
    async def authorize_account(
        self, queries: AccountQueries, phone: str, code: str
    ) -> bool:
        """
        Authorize account with received code.

        :param queries: Database queries executor
        :param phone: Phone number
        :param code: Authorization code
        :return: True if authorization successful
        """
        try:
            phone = self._normalize_phone(phone)
            logger.info(f"Starting authorization for {phone}")

            account = await queries.get_account_by_phone(phone)
            if not account:
                logger.error(f"No account found for phone: {phone}")
                return False

            if account.status != AccountStatus.code_requested:
                logger.error(f"Invalid account state for authorization: {phone}")
                return False

            client = await self.get_client(account)
            if not client:
                return False

            if await client.sign_in(code):
                session_string = await client.export_session_string()
                await queries.update_session(account.id, session_string)
                await queries.update_status(account.id, AccountStatus.active)
                logger.info(f"Successfully authorized account {phone}")
                return True

            return False

        except Exception as e:
            logger.error(f"Error in authorize_account: {e}", exc_info=True)
            return False

    @with_queries(AccountQueries)
    async def request_code(self, queries: AccountQueries, phone: str) -> bool:
        """
        Request authorization code for account.

        :param queries: Database queries executor
        :param phone: Phone number
        :return: True if code request successful
        """
        try:
            phone = self._normalize_phone(phone)
            account = await queries.get_account_by_phone(phone)
            if not account:
                logger.error(f"No account found for phone: {phone}")
                return False

            client = await self.get_client(account)
            if not client:
                return False

            if await client.connect():
                await queries.update_status(account.id, AccountStatus.code_requested)
                logger.info(f"Successfully requested code for {phone}")
                return True

            return False

        except Exception as e:
            logger.error(f"Error in request_code: {e}", exc_info=True)
            return False

    @with_queries(AccountQueries)
    async def disable_account(self, queries: AccountQueries, account_id: int) -> None:
        """
        Disable account and disconnect its client.

        :param queries: Database queries executor
        :param account_id: ID of the account to disable
        """
        try:
            client_manager = await self._get_client_manager()
            await client_manager.disconnect_client(account_id)
            await queries.update_status(account_id, AccountStatus.disabled)
            logger.info(f"Account {account_id} disabled")
        except Exception as e:
            logger.error(f"Error disabling account {account_id}: {e}", exc_info=True)
            raise

    async def cleanup(self) -> None:
        """
        Cleanup resources when shutting down.
        Disconnects all clients and performs necessary cleanup.
        """
        try:
            if self._client_manager:
                await self._client_manager.cleanup()
        except Exception as e:
            logger.error(f"Error in cleanup: {e}", exc_info=True)
