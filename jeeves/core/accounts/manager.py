"""Account manager."""

# Standard library
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional

# Core dependencies
from core.db import with_queries

from .client_manager import ClientManager

# Local imports
from .models.account import Account, AccountStatus
from .queries.account import AccountQueries
from .queries.profile import ProfileQueries

# Type hints
if TYPE_CHECKING:
    from pyrogram.types import User

    from .client import AccountClient
    from .models.profile import AccountProfile

logger = logging.getLogger(__name__)


class AccountManager:
    """Account manager."""

    def __init__(self):
        self.client_manager = ClientManager()

    @with_queries(AccountQueries)
    async def request_code(self, phone: str, queries: AccountQueries) -> bool:
        """Request authorization code."""
        try:
            account = await self._get_or_create_account(phone, queries)
            if not account:
                return False

            async with self._get_client(phone) as client:
                if not client or not await client.send_code():
                    return False

                account.status = AccountStatus.code_requested
                queries.session.add(account)
                return True

        except Exception as e:
            logger.error(f"Error in request_code for {phone}: {e}", exc_info=True)
            return False

    @with_queries(AccountQueries)
    async def authorize_account(
        self, phone: str, code: str, queries: AccountQueries
    ) -> bool:
        """Authorize account with code."""
        try:
            account = await self._get_or_create_account(phone, queries)
            if not account:
                return False

            async with self._get_client(phone) as client:
                if not client:
                    return False

                session_string = await client.sign_in(code)
                if not session_string:
                    return False

                self._update_account_status(account, session_string)
                queries.session.add(account)
                await self.client_manager.release_client(phone)
                return True

        except Exception as e:
            logger.error(f"Error in authorize_account for {phone}: {e}", exc_info=True)
            return False

    @with_queries(ProfileQueries)
    async def sync_account_profile(self, phone: str, queries: ProfileQueries) -> bool:
        """Sync account profile with Telegram."""
        try:
            account = await self._get_or_create_account(phone)
            if not account:
                return False

            async with self._get_client(phone, account.session_string) as client:
                if not client:
                    return False

                me = await client.client.get_me()
                if not me:
                    return False

                profile = await self._get_or_create_profile(account.id, queries)
                if not profile:
                    return False

                profile_data = await self._get_profile_data(client, me)
                await self._update_profile_data(profile, **profile_data)
                queries.session.add(profile)

                logger.info(f"Successfully synced profile for {phone}")
                return True

        except Exception as e:
            logger.error(f"Error syncing profile for {phone}: {e}", exc_info=True)
            return False

    @with_queries(ProfileQueries)
    async def update_account_profile(
        self, phone: str, queries: ProfileQueries, **profile_data
    ) -> bool:
        """Update account profile both in Telegram and database."""
        try:
            account = await self._get_or_create_account(phone)
            if not account:
                return False

            async with self._get_client(phone, account.session_string) as client:
                if not client or not await client.update_profile(**profile_data):
                    return False

                profile = await self._get_or_create_profile(account.id, queries)
                if not profile:
                    return False

                await self._update_profile_data(profile, **profile_data)
                queries.session.add(profile)
                return True

        except Exception as e:
            logger.error(f"Error updating profile for {phone}: {e}")
            return False

    @with_queries(AccountQueries)
    async def increment_messages(
        self, account_id: int, queries: AccountQueries
    ) -> bool:
        """Increment messages count for account."""
        try:
            account = await queries.get_account_by_id(account_id)
            if not account:
                return False

            self._increment_account_messages(account)
            queries.session.add(account)
            return True

        except Exception as e:
            logger.error(f"Failed to increment messages for account {account_id}: {e}")
            return False

    # Helper methods
    @staticmethod
    async def _get_or_create_account(
        phone: str, queries: AccountQueries
    ) -> Optional[Account]:
        """Get or create account by phone number."""
        try:
            account = await queries.get_account_by_phone(phone)
            if not account:
                account = Account(phone=phone)
                queries.session.add(account)
            return account
        except Exception as e:
            logger.error(f"Error getting/creating account {phone}: {e}", exc_info=True)
            return None

    @staticmethod
    async def _get_or_create_profile(
        account_id: int, queries: ProfileQueries
    ) -> Optional["AccountProfile"]:
        """Get or create profile for account."""
        try:
            return await queries.get_account_profile(
                account_id
            ) or await queries.create_profile(account_id)
        except Exception as e:
            logger.error(
                f"Error getting/creating profile for account {account_id}: {e}"
            )
            return None

    @asynccontextmanager
    async def _get_client(self, phone: str, session_string: Optional[str] = None):
        """Get client with automatic cleanup."""
        client = None
        try:
            client = await self.client_manager.get_client(phone, session_string)
            yield client
        finally:
            if client:
                await client.stop()

    @staticmethod
    async def _get_profile_data(client: "AccountClient", me: "User") -> dict:
        """Get profile data from Telegram."""
        bio = None
        try:
            full_user = await client.client.get_chat(me.id)
            bio = getattr(full_user, "bio", None)
        except Exception as e:
            logger.error(f"Error getting bio: {e}")

        return {
            "username": me.username,
            "first_name": me.first_name,
            "last_name": me.last_name,
            "bio": bio,
        }

    @staticmethod
    async def _update_profile_data(profile: "AccountProfile", **kwargs) -> None:
        """Update profile data with current timestamp."""
        now = datetime.now(timezone.utc)
        profile.update_data(**kwargs, synced_at=now, telegram_update=now)

    @staticmethod
    def _update_account_status(account: Account, session_string: str) -> None:
        """Update account status after successful authorization."""
        account.session_string = session_string
        account.status = AccountStatus.active
        account.last_used_at = datetime.now(timezone.utc)

    @staticmethod
    def _increment_account_messages(account: Account) -> None:
        """Increment account message counters."""
        account.messages_sent += 1
        account.daily_messages += 1
        account.last_used_at = datetime.now(timezone.utc)
