import asyncio
import logging
from typing import Dict, Optional

from .client import AccountClient
from .models import Account

logger = logging.getLogger(__name__)


class AccountClientManager:
    """
    Internal component for managing Telegram client connections.
    Maintains persistent connections and handles client lifecycle.
    Implements Singleton pattern to ensure only one instance exists.
    """

    _instance = None
    _lock = asyncio.Lock()

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(AccountClientManager, cls).__new__(cls)
            # Initialize instance attributes
            cls._instance._initialized = False
        return cls._instance

    async def __aenter__(self):
        """Support for async context manager"""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Cleanup when used as context manager"""
        await self.cleanup()

    def __init__(self):
        """
        Initialize the manager if it hasn't been initialized yet.
        This method might be called multiple times due to singleton pattern,
        so we need to guard against multiple initializations.
        """
        if not getattr(self, "_initialized", False):
            self._clients: Dict[int, AccountClient] = {}
            self._connection_tasks: Dict[int, asyncio.Task] = {}
            self._instance_lock = asyncio.Lock()  # Lock for instance methods
            self._initialized = True

    @classmethod
    async def get_instance(cls) -> "AccountClientManager":
        """
        Get singleton instance of AccountClientManager.
        This method is not strictly necessary with __new__ implementation,
        but provides explicit async-safe way to get instance.

        :return: AccountClientManager instance
        """
        async with cls._lock:
            if cls._instance is None:
                cls._instance = cls()
            return cls._instance

    async def get_client(self, account: Account) -> Optional[AccountClient]:
        """
        Get or create a client for the account.
        Ensures only one client exists per account.

        :param account: Account to get/create client for
        :return: AccountClient instance or None if creation failed
        """
        async with self._instance_lock:
            if account.id in self._clients:
                return self._clients[account.id]

            try:
                client = AccountClient(account)
                if await client.connect():
                    self._clients[account.id] = client
                    # Start connection maintenance task
                    self._start_connection_maintenance(account.id, client)
                    return client
                else:
                    logger.error(f"Failed to connect client for account {account.id}")
                    return None
            except Exception as e:
                logger.error(f"Error creating client for account {account.id}: {e}")
                return None

    async def disconnect_client(self, account_id: int) -> None:
        """
        Disconnect and remove client for the account.

        :param account_id: ID of the account to disconnect
        """
        async with self._instance_lock:
            if account_id in self._clients:
                # Cancel connection maintenance task
                if account_id in self._connection_tasks:
                    self._connection_tasks[account_id].cancel()
                    try:
                        await self._connection_tasks[account_id]
                    except asyncio.CancelledError:
                        pass
                    del self._connection_tasks[account_id]

                # Disconnect client
                client = self._clients[account_id]
                try:
                    if client.client and client.client.is_connected:
                        await client.client.disconnect()
                except Exception as e:
                    logger.error(
                        f"Error disconnecting client for account {account_id}: {e}"
                    )

                del self._clients[account_id]

    def _start_connection_maintenance(
        self, account_id: int, client: AccountClient
    ) -> None:
        """
        Start background task for maintaining client connection.

        :param account_id: ID of the account
        :param client: AccountClient instance to maintain
        """
        if account_id in self._connection_tasks:
            self._connection_tasks[account_id].cancel()

        task = asyncio.create_task(self._maintain_connection(account_id, client))
        self._connection_tasks[account_id] = task

    async def _maintain_connection(
        self, account_id: int, client: AccountClient
    ) -> None:
        """
        Background task that maintains client connection.
        Automatically reconnects if connection is lost.

        :param account_id: ID of the account
        :param client: AccountClient instance to maintain
        """
        while True:
            try:
                if not client.client or not client.client.is_connected:
                    logger.info(f"Reconnecting client for account {account_id}")
                    await client.connect()
                await asyncio.sleep(60)  # Check connection every minute
            except asyncio.CancelledError:
                logger.info(
                    f"Connection maintenance cancelled for account {account_id}"
                )
                break
            except Exception as e:
                logger.error(
                    f"Error in connection maintenance for account {account_id}: {e}"
                )
                await asyncio.sleep(5)  # Wait before retry

    async def cleanup(self) -> None:
        """
        Disconnect all clients and cleanup resources.
        Should be called when shutting down the application.
        """
        async with self._instance_lock:
            for account_id in list(self._clients.keys()):
                await self.disconnect_client(account_id)
