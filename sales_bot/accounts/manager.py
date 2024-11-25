import logging
from typing import Optional

from db.models import AccountStatus
from db.queries import AccountQueries, get_db

from .client import AccountClient
from .models import Account
from .safety import AccountSafety

logger = logging.getLogger(__name__)


class AccountManager:
    def __init__(self, db):
        self.db = db
        self.queries = AccountQueries(self.db)
        self.safety = AccountSafety()
        self._active_clients: dict[int, AccountClient] = {}

    def _normalize_phone(self, phone: str) -> str:
        """Normalize phone number to standard format"""
        return (
            phone.strip()
            .replace("+", "")
            .replace(" ", "")
            .replace("-", "")
            .replace("(", "")
            .replace(")", "")
        )

    async def add_account(self, phone_number: str) -> Account:
        """
        Добавление нового аккаунта в базу данных

        :param phone_number: Номер телефона аккаунта
        :return: Созданный аккаунт
        """
        try:
            async with get_db() as session:
                queries = AccountQueries(session)
                account = await queries.create_account(phone_number)
                return account

        except Exception as e:
            logger.error(f"Error adding account: {e}", exc_info=True)
            raise

    async def authorize_account(self, phone: str, code: str) -> bool:
        """Authorize account with received code"""
        try:
            phone = self._normalize_phone(phone)
            logger.info(f"Starting authorization for {phone}")

            async with get_db() as session:
                queries = AccountQueries(session)
                account = await queries.get_account_by_phone(phone)

                if not account:
                    logger.error(f"No account found for phone: {phone}")
                    return False

                if account.status != AccountStatus.code_requested:
                    logger.error(f"Invalid account state for authorization: {phone}")
                    return False

                # Get existing client that has the phone code hash
                client = self._active_clients.get(account.id)
                if not client:
                    logger.error(
                        f"No active client found for account {account.id} ({phone})"
                    )
                    return False

                # Authorize with stored phone code hash
                if not await client.sign_in(code):
                    logger.error(f"Failed to sign in account {account.id} ({phone})")
                    return False

                # Export and store session string
                session_string = await client.export_session_string()
                await queries.update_account_session(account.id, session_string)
                await queries.update_account_status(account.id, AccountStatus.active)
                await session.commit()

                logger.info(f"Successfully authorized account {account.id} ({phone})")
                return True

        except Exception:
            logger.error(f"Authorization failed for account: {phone}", exc_info=True)
            return False

    async def get_available_account(self) -> Optional[Account]:
        """Get account available for sending messages"""
        try:
            async with get_db() as session:
                queries = AccountQueries(session)
                accounts = await queries.get_active_accounts()

                for account in accounts:
                    if account.can_be_used and self.safety.can_send_message(account):
                        return account

            return None

        except Exception as e:
            logger.error(f"Failed to get available account: {e}", exc_info=True)
            return None

    async def send_message(self, account: Account, username: str, text: str) -> bool:
        """Send message using specified account"""
        try:
            if not account.can_be_used:
                logger.error(
                    f"Account {account.phone} is not available for sending messages"
                )
                return False

            # Check safety
            if not self.safety.can_send_message(account):
                return False

            # Get or create client
            client = self._active_clients.get(account.id)
            if not client:
                client = AccountClient(account)
                if not await client.connect():
                    return False
                self._active_clients[account.id] = client

            # Send message
            success = await client.send_message(username, text)
            if success:
                # Safety update
                self.safety.record_message(account)

            return success

        except Exception as e:
            logger.error(
                f"Failed to send message from {account.phone}: {e}", exc_info=True
            )
            return False

    async def update_account_status(self, phone: str, status: AccountStatus):
        """Update account status"""
        try:
            phone = self._normalize_phone(phone)
            account = await self.queries.get_account_by_phone(phone)
            if not account:
                return

            # Update status
            async with get_db() as session:
                queries = AccountQueries(session)
                await queries.update_account_status(account.id, status)

            # Close client if needed
            if status in [AccountStatus.blocked, AccountStatus.disabled]:
                client = self._active_clients.pop(account.id, None)
                if client:
                    await client.disconnect()

        except Exception as e:
            logger.error(f"Failed to update status for {phone}: {e}", exc_info=True)

    async def request_code(self, phone: str) -> bool:
        """Request authorization code for account"""
        try:
            phone = self._normalize_phone(phone)
            logger.info(f"Requesting code for normalized phone: {phone}")

            async with get_db() as session:
                queries = AccountQueries(session)
                account = await queries.get_account_by_phone(phone)

                logger.debug(f"Found account: {account}")
                if not account:
                    logger.error(f"No account found for phone: {phone}")
                    return False

                # Create and connect client
                logger.debug(f"Creating client for account {account.id} ({phone})")
                client = AccountClient(account)

                logger.debug(f"Connecting client for account {account.id} ({phone})")
                if not await client.connect():
                    logger.error(
                        f"Failed to connect client for account {account.id} ({phone})"
                    )
                    return False

                # Store active client for later use
                self._active_clients[account.id] = client
                logger.info(
                    "Successfully stored active client "
                    f"for account {account.id} ({phone})"
                )

                # Verify client state
                logger.debug(f"Client state for {phone}:")
                logger.debug(f"- Connected: {client.client.is_connected}")
                logger.debug(
                    f"- Phone code hash: {'Yes' if client._phone_code_hash else 'No'}"
                )
                logger.debug(f"- Account status: {account.status}")

                # Update account status in database
                await queries.update_account_status(
                    account.id, AccountStatus.code_requested
                )
                await session.commit()

                return True

        except Exception as e:
            logger.error(
                f"Failed to request code for account {phone}: {e}", exc_info=True
            )
            return False

    async def resend_code(self, phone: str) -> bool:
        """Resend authorization code for account"""
        try:
            phone = self._normalize_phone(phone)
            account = await self.queries.get_account_by_phone(phone)
            if not account:
                return False

            # Проверяем текущее состояние
            if account.status not in [AccountStatus.new, AccountStatus.code_requested]:
                logger.error(
                    f"Cannot resend code for account {phone} in state {account.status}"
                )
                return False

            # Создаем клиент и запрашиваем код
            client = AccountClient(account)
            if not await client.connect():
                return False

            return True

        except Exception as e:
            logger.error(f"Failed to resend code for {phone}: {e}", exc_info=True)
            return False
