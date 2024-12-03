"""Client manager for Telegram accounts."""

import asyncio
import logging
from typing import Dict, Optional

from core.db import with_queries

from .client import AccountClient
from .models import AccountStatus
from .queries.account import AccountQueries

logger = logging.getLogger(__name__)


class ClientManager:
    """Centralized manager for Telegram clients."""

    _instance = None
    _initialized = False

    def __new__(cls):
        """Ensure single instance creation."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        """Initialize manager."""
        if not ClientManager._initialized:
            self._clients: Dict[str, AccountClient] = {}
            self._lock = asyncio.Lock()
            ClientManager._initialized = True

    @with_queries(AccountQueries)
    async def get_client(
        self,
        phone: str,
        session_string: Optional[str] = None,
        queries: Optional[AccountQueries] = None,
    ) -> Optional[AccountClient]:
        """
        Get or create client for phone number.

        Args:
            phone: Phone number
            session_string: Optional session string for existing sessions
            queries: Optional AccountQueries instance

        Returns:
            AccountClient if successful, None otherwise
        """
        async with self._lock:
            logger.debug(f"Getting client for {phone}")

            if phone in self._clients:
                logger.debug(f"Returning existing client for {phone}")
                return self._clients[phone]

            # Check account status if queries provided
            check_auth = True
            if queries:
                account = await queries.get_account_by_phone(phone)
                if account and account.status != AccountStatus.active:
                    logger.debug(f"Account {phone} is not active, skipping auth check")
                    check_auth = False

            # Create new client
            client = AccountClient(phone, session_string)
            if await client.start(check_auth=check_auth):
                logger.debug(f"Successfully created client for {phone}")
                self._clients[phone] = client
                return client

            logger.debug(f"Failed to create client for {phone}")
            await client.stop()
            return None

    @with_queries(AccountQueries)
    async def release_client(self, phone: str, queries: AccountQueries):
        """
        Release client for phone number.

        Args:
            phone: Phone number to release
            queries: AccountQueries instance
        """
        async with self._lock:
            if phone in self._clients:
                client = self._clients[phone]
                logger.debug(f"Releasing client for {phone}")

                # Save session string if it has changed
                if client.session_string:
                    account = await queries.get_account_by_phone(phone)
                    if account and account.session_string != client.session_string:
                        logger.debug(f"Updating session string for {phone}")
                        account.session_string = client.session_string
                        queries.session.add(account)

                await client.stop()
                del self._clients[phone]
                logger.debug(f"Client for {phone} released")

    async def stop_all(self):
        """Stop all active clients."""
        async with self._lock:
            logger.debug(f"Stopping all clients ({len(self._clients)} active)")
            for client in self._clients.values():
                await client.stop()
            self._clients.clear()
            logger.debug("All clients stopped")

    def __len__(self) -> int:
        """Get number of active clients."""
        return len(self._clients)

    @with_queries(AccountQueries)
    async def get_any_client(self, queries: AccountQueries) -> Optional[AccountClient]:
        """Get any available client from active accounts."""
        try:
            account = await queries.get_any_active_account()
            if not account:
                logger.error("No available accounts found")
                return None

            logger.debug(f"Using account {account.phone}")
            return await self.get_client(account.phone, account.session_string)

        except Exception as e:
            logger.error(f"Error getting any client: {e}", exc_info=True)
            return None
