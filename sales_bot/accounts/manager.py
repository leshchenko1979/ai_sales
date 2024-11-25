import asyncio
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
        self.queries = AccountQueries(db)
        self.safety = AccountSafety()
        self._active_clients: dict[int, AccountClient] = {}

    async def add_account(self, phone: str) -> Optional[Account]:
        """Add new account to system"""
        try:

            # Check if account already exists
            existing = await self.queries.get_account_by_phone(phone)
            if existing:
                logger.warning(f"Account {phone} already exists")
                return existing

            # Create new account
            async with get_db() as session:
                queries = AccountQueries(session)
                account = await queries.create_account(phone)
                if not account:
                    return None

            # Create and connect client with retries
            for attempt in range(3):
                try:
                    client = AccountClient(account)
                    if await client.connect():
                        # Request authorization code
                        await client.client.send_code(phone)
                        return account

                    await asyncio.sleep(5)  # Wait before retry

                except Exception as e:
                    logger.warning(f"Attempt {attempt + 1} failed for {phone}: {e}")
                    if attempt < 2:  # Don't sleep on last attempt
                        await asyncio.sleep(5)
                    continue

            logger.error(f"Failed to initialize account {phone} after 3 attempts")
            await queries.update_account_status_by_id(
                account.id, AccountStatus.disabled
            )
            return None

        except Exception as e:
            logger.error(f"Failed to add account {phone}: {e}", exc_info=True)
            return None

    async def authorize_account(self, phone: str, code: str) -> bool:
        """Authorize account with received code"""
        try:
            account = await self.queries.get_account_by_phone(phone)
            if not account:
                return False

            client = AccountClient(account)
            if not await client.connect():
                return False

            # Authorize and save session
            session_string = await client.authorize(code)
            if not session_string:
                return False

            # Update account in DB
            return await self.queries.update_session(account.id, session_string)

        except Exception as e:
            logger.error(f"Failed to authorize account {phone}: {e}", exc_info=True)
            return False

    async def get_available_account(self) -> Optional[Account]:
        """Get account available for sending messages"""
        accounts = await self.queries.get_active_accounts()

        for account in accounts:
            if account.is_available and self.safety.can_send_message(account):
                return account

        return None

    async def send_message(self, account: Account, username: str, text: str) -> bool:
        """Send message using specified account"""
        try:
            # Get or create client
            client = self._active_clients.get(account.id)
            if not client:
                client = AccountClient(account)
                if not await client.connect():
                    return False
                self._active_clients[account.id] = client

            # Check safety
            if not self.safety.can_send_message(account):
                return False

            # Send message
            success = await client.send_message(username, text)
            if success:
                # Update account stats
                await self.queries.increment_messages(account.id)
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
            await self.queries.update_account_status(phone, status)
        except Exception as e:
            logger.error(
                f"Failed to update account status for {phone}: {e}", exc_info=True
            )

    async def resend_code(self, phone: str) -> bool:
        """Resend authorization code for account"""
        try:
            account = await self.queries.get_account_by_phone(phone)
            if not account:
                logger.error(f"Account {phone} not found")
                return False

            client = AccountClient(account)
            if not await client.connect():
                return False

            # Request new code
            await client.client.send_code(phone)
            return True

        except Exception as e:
            logger.error(
                f"Failed to resend code for account {phone}: {e}", exc_info=True
            )
            return False
