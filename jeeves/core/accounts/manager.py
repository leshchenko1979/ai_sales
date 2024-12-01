"""Account manager."""

import logging
from datetime import datetime, timezone
from typing import List, Optional

from core.accounts.client_manager import ClientManager
from core.accounts.models.account import Account, AccountStatus
from core.accounts.queries.account import AccountQueries
from core.accounts.queries.profile import ProfileQueries
from core.db import with_queries

logger = logging.getLogger(__name__)


class AccountManager:
    """Account manager."""

    def __init__(self):
        """Initialize manager."""
        self.client_manager = ClientManager()
        logger.debug("AccountManager initialized")

    @with_queries(AccountQueries)
    async def get_or_create_account(
        self, phone: str, queries: AccountQueries
    ) -> Optional[Account]:
        """
        Get or create account.

        Args:
            phone: Phone number
            queries: Account queries

        Returns:
            Account if successful, None otherwise
        """
        try:
            logger.debug(f"Getting or creating account for {phone}")
            # Get or create account
            account = await queries.get_account_by_phone(phone)
            if not account:
                logger.debug(f"Creating new account for {phone}")
                account = Account(phone=phone)
                queries.session.add(account)
            else:
                logger.debug(f"Found existing account for {phone}: {account}")
            return account

        except Exception as e:
            logger.error(f"Error getting/creating account {phone}: {e}", exc_info=True)
            return None

    @with_queries((AccountQueries, ProfileQueries))
    async def update_account_profile(
        self,
        phone: str,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
        bio: Optional[str] = None,
        photo_path: Optional[str] = None,
        account_queries: AccountQueries = None,
        profile_queries: ProfileQueries = None,
    ) -> bool:
        """Update account profile both in Telegram and database."""
        try:
            # Get account
            account = await self.get_or_create_account(phone)
            if not account:
                return False

            # Update Telegram profile
            client = await self.client_manager.get_client(phone, account.session_string)
            if not client:
                return False

            if not await client.update_profile(
                first_name=first_name,
                last_name=last_name,
                bio=bio,
                photo_path=photo_path,
            ):
                return False

            # Get or create profile
            profile = await profile_queries.get_account_profile(
                account.id
            ) or await profile_queries.create_profile(account.id)
            if not profile:
                return False

            # Update profile data
            if first_name is not None:
                profile.first_name = first_name
            if last_name is not None:
                profile.last_name = last_name
            if bio is not None:
                profile.bio = bio
            if photo_path is not None:
                profile.photo_path = photo_path

            profile.is_synced = True
            profile.last_synced_at = datetime.now(timezone.utc)
            profile_queries.session.add(profile)

            return True

        except Exception as e:
            logger.error(f"Error updating profile for {phone}: {e}")
            return False

    @with_queries((AccountQueries, ProfileQueries))
    async def get_account_profile(
        self,
        phone: str,
        account_queries: AccountQueries,
        profile_queries: ProfileQueries,
    ) -> Optional[dict]:
        """Get account profile info."""
        try:
            # Get account
            account = await self.get_or_create_account(phone)
            if not account:
                return None

            # Get current Telegram profile
            client = await self.client_manager.get_client(phone, account.session_string)
            if not client:
                return None

            profile = await client.get_profile()
            if not profile:
                return None

            # Get database profile
            db_profile = await profile_queries.get_account_profile(account.id)
            if db_profile:
                profile["photo_path"] = db_profile.photo_path

            return profile

        except Exception as e:
            logger.error(f"Error getting profile for {phone}: {e}")
            return None

    @with_queries((AccountQueries, ProfileQueries))
    async def sync_account_profile(
        self,
        phone: str,
        account_queries: AccountQueries,
        profile_queries: ProfileQueries,
    ) -> bool:
        """Sync account profile with Telegram."""
        try:
            # Get account
            account = await self.get_or_create_account(phone)
            if not account:
                return False

            # Get current profile from Telegram
            client = await self.client_manager.get_client(phone, account.session_string)
            if not client:
                return False

            try:
                # Get Telegram profile
                me = await client.client.get_me()
                if not me:
                    return False

                # Get or create database profile
                profile = await profile_queries.get_account_profile(
                    account.id
                ) or await profile_queries.create_profile(account.id)
                if not profile:
                    return False

                # Update profile data
                profile.username = me.username or ""
                profile.first_name = me.first_name or ""
                profile.last_name = me.last_name or ""
                profile.bio = me.bio or ""
                profile.is_synced = True
                profile.last_synced_at = datetime.now(timezone.utc)
                profile.last_telegram_update = datetime.now(timezone.utc)

                profile_queries.session.add(profile)
                return True

            finally:
                await client.stop()

        except Exception as e:
            logger.error(f"Error syncing profile for {phone}: {e}")
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

            account.messages_sent += 1
            account.daily_messages += 1
            account.last_used_at = datetime.now(timezone.utc)
            queries.session.add(account)
            return True

        except Exception as e:
            logger.error(f"Failed to increment messages for account {account_id}: {e}")
            return False

    @with_queries((AccountQueries, ProfileQueries))
    async def update_profile(
        self,
        account_id: int,
        account_queries: AccountQueries,
        profile_queries: ProfileQueries,
    ) -> bool:
        """Update account profile from Telegram."""
        try:
            account = await account_queries.get_account_by_id(account_id)
            if not account:
                return False

            profile = await profile_queries.get_account_profile(account_id)
            if not profile:
                return False

            profile.last_synced_at = datetime.now(timezone.utc)
            profile_queries.session.add(profile)
            return True

        except Exception as e:
            logger.error(f"Failed to update profile for account {account_id}: {e}")
            return False

    @with_queries(AccountQueries)
    async def request_code(self, phone: str, queries: AccountQueries) -> bool:
        """
        Request authorization code.

        Args:
            phone: Phone number
            queries: Account queries

        Returns:
            bool: True if successful
        """
        try:
            logger.debug(f"Starting code request for {phone}")

            # Get account
            account = await self.get_or_create_account(phone)
            if not account:
                logger.error(f"Failed to get/create account for {phone}")
                return False

            logger.debug(f"Current account status: {account.status}")

            # Get client
            logger.debug(f"Getting client for {phone}")
            client = await self.client_manager.get_client(phone)
            if not client:
                logger.error(f"Failed to get client for {phone}")
                return False

            try:
                # Send code
                logger.debug(f"Sending code to {phone}")
                if not await client.send_code():
                    logger.error(f"Failed to send code to {phone}")
                    return False

                # Update status
                logger.debug(f"Updating account status for {phone}")
                account.status = AccountStatus.code_requested
                queries.session.add(account)
                logger.debug(f"Code successfully requested for {phone}")
                return True

            except Exception as e:
                logger.error(f"Error requesting code: {e}", exc_info=True)
                return False

        except Exception as e:
            logger.error(f"Error in request_code for {phone}: {e}", exc_info=True)
            return False

    @with_queries(AccountQueries)
    async def authorize_account(
        self, phone: str, code: str, queries: AccountQueries
    ) -> bool:
        """
        Authorize account with code.

        Args:
            phone: Phone number
            code: Authorization code
            queries: Account queries

        Returns:
            bool: True if successful
        """
        try:
            logger.debug(f"Starting authorization for {phone}")

            # Get account
            account = await self.get_or_create_account(phone)
            if not account:
                logger.error(f"Failed to get/create account for {phone}")
                return False

            logger.debug(f"Current account status: {account.status}")

            # Get client
            logger.debug(f"Getting client for {phone}")
            client = await self.client_manager.get_client(phone)
            if not client:
                logger.error(f"Failed to get client for {phone}")
                return False

            try:
                # Sign in
                logger.debug(f"Attempting to sign in {phone}")
                session_string = await client.sign_in(code)
                if not session_string:
                    logger.error(f"Failed to sign in {phone}")
                    return False

                # Update account
                logger.debug(f"Updating account data for {phone}")
                account.session_string = session_string
                account.status = AccountStatus.active
                account.last_used = datetime.now(timezone.utc)
                queries.session.add(account)

                logger.debug(f"Successfully authorized {phone}")
                return True

            except Exception as e:
                logger.error(f"Error in sign in: {e}", exc_info=True)
                return False

            finally:
                # Only release client if authorization was successful
                if account.status == AccountStatus.active:
                    logger.debug(f"Releasing client for {phone} after successful auth")
                    await self.client_manager.release_client(phone)
                else:
                    logger.debug(
                        f"Keeping client for {phone} as auth was not successful"
                    )

        except Exception as e:
            logger.error(f"Error in authorize_account for {phone}: {e}", exc_info=True)
            return False

    @with_queries(AccountQueries)
    async def get_available_account(self, queries: AccountQueries) -> Optional[Account]:
        """
        Get available account.

        Args:
            queries: Account queries

        Returns:
            Account if found, None otherwise
        """
        try:
            # Get active account with least recent usage
            account = await queries.get_available_account()
            if not account:
                return None

            # Update last used
            account.last_used = datetime.now(timezone.utc)
            queries.session.add(account)

            return account

        except Exception as e:
            logger.error(f"Error getting available account: {e}", exc_info=True)
            return None

    @with_queries(AccountQueries)
    async def check_flood_wait(self, phone: str, queries: AccountQueries) -> bool:
        """
        Check if account is in flood wait.

        Args:
            phone: Phone number
            queries: Account queries

        Returns:
            bool: True if successful
        """
        try:
            # Get account
            account = await self.get_or_create_account(phone)
            if not account:
                return False

            # Get client
            client = await self.client_manager.get_client(phone, account.session_string)
            if not client:
                return False

            try:
                # Check flood wait
                flood_wait = await client.check_flood_wait()

                # Update account
                account.flood_wait_until = flood_wait or None
                queries.session.add(account)

                return True

            finally:
                await self.client_manager.release_client(phone)

        except Exception as e:
            logger.error(f"Error checking flood wait for {phone}: {e}", exc_info=True)
            return False

    @with_queries(AccountQueries)
    async def get_available_accounts(self, queries: AccountQueries) -> List[Account]:
        """Get list of available accounts."""
        try:
            return await queries.get_available_accounts()
        except Exception as e:
            logger.error(f"Failed to get available accounts: {e}")
            return []
