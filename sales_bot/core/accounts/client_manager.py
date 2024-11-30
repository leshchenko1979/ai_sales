"""Client manager for Telegram accounts."""

import asyncio
import logging
from typing import Dict, Optional

from core.accounts.queries.account import AccountQueries
from core.db import with_queries

from .client import AccountClient

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

    async def get_client(
        self, phone: str, session_string: Optional[str] = None
    ) -> Optional[AccountClient]:
        """
        Get or create client for phone number.

        Args:
            phone: Phone number
            session_string: Optional session string for existing sessions

        Returns:
            AccountClient if successful, None otherwise
        """
        async with self._lock:
            if phone not in self._clients:
                client = AccountClient(phone, session_string)
                if await client.start():
                    self._clients[phone] = client
                else:
                    await client.stop()
                    return None
            return self._clients.get(phone)

    @with_queries(AccountQueries)
    async def release_client(self, phone: str, queries: AccountQueries):
        """
        Release client for phone number.

        Args:
            phone: Phone number to release
        """
        async with self._lock:
            if phone in self._clients:
                client = self._clients[phone]
                # Save session string if it has changed
                if client.session_string:
                    account = await queries.get_account_by_phone(phone)
                    if account and account.session_string != client.session_string:
                        account.session_string = client.session_string
                        queries.session.add(account)
                await client.stop()
                del self._clients[phone]

    async def stop_all(self):
        """Stop all active clients."""
        async with self._lock:
            for client in self._clients.values():
                await client.stop()
            self._clients.clear()

    def __len__(self) -> int:
        """Get number of active clients."""
        return len(self._clients)
