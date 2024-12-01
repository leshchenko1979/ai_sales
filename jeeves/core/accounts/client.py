"""Telegram client for account operations."""

import logging
from datetime import datetime
from typing import Optional

from infrastructure.config import API_HASH, API_ID
from pyrogram import Client
from pyrogram.errors import AuthKeyDuplicated, AuthKeyUnregistered
from utils.phone import normalize_phone

from .decorators import (
    handle_auth_errors,
    handle_flood_wait,
    log_operation,
    require_client,
)

logger = logging.getLogger(__name__)


class AccountClient:
    """Telegram client for account operations."""

    def __init__(self, phone: str, session_string: Optional[str] = None):
        """Initialize client."""
        self.phone = normalize_phone(phone)
        self.session_string = session_string
        self.client: Optional[Client] = None
        self._initialized = False
        self._connected = False
        self.phone_code_hash = None

    # Core Operations
    @log_operation("client_start")
    async def start(self, check_auth: bool = True) -> bool:
        """Start client and optionally verify authorization."""
        try:
            if self._initialized and self.client:
                return True

            logger.debug(f"Starting client for {self.phone} (check_auth={check_auth})")

            # Create client instance
            if not await self._create_client():
                logger.error(f"Failed to create client for {self.phone}")
                return False

            # Connect to Telegram
            if not await self._connect_client():
                logger.error(f"Failed to connect client for {self.phone}")
                return False

            if not check_auth:
                logger.debug(f"Skipping auth check for {self.phone}")
                self._initialized = True
                return True

            if self.session_string and not await self._verify_session():
                return False

            self._initialized = True
            return True

        except (AuthKeyDuplicated, AuthKeyUnregistered) as e:
            logger.warning(f"Invalid session for {self.phone}: {e}")
            await self.stop()
            return False
        except Exception as e:
            logger.error(f"Error starting client for {self.phone}: {e}", exc_info=True)
            await self.stop()
            return False

    @log_operation("client_stop")
    async def stop(self) -> None:
        """Stop client and cleanup resources."""
        if not self.client:
            logger.debug(f"No client instance for {self.phone}")
            return

        try:
            await self._disconnect_client()
            await self._terminate_client()
        except Exception as e:
            logger.error(f"Error stopping client for {self.phone}: {e}")
        finally:
            self.client = None
            self._initialized = False
            self._connected = False

    # Authentication Operations
    @log_operation("send_code")
    @handle_auth_errors("send_code")
    @handle_flood_wait("send_code")
    @require_client()
    async def send_code(self) -> bool:
        """Send authorization code to phone number."""
        if not await self._connect_client():
            return False

        sent = await self.client.send_code(self.phone)
        self.phone_code_hash = sent.phone_code_hash
        logger.debug(f"Sent code to {self.phone}")
        return True

    @log_operation("sign_in")
    @handle_auth_errors("sign_in")
    @handle_flood_wait("sign_in")
    @require_client()
    async def sign_in(self, code: str) -> Optional[str]:
        """Sign in with received code."""
        if not self._initialized:
            return None

        await self.client.sign_in(
            phone_number=self.phone,
            phone_code_hash=self.phone_code_hash,
            phone_code=code,
        )

        session_string = await self.client.export_session_string()
        self.session_string = session_string
        return session_string

    # Message Operations
    @log_operation("send_message")
    @handle_flood_wait("send_message", sleep=True)
    @require_client(initialized=True)
    async def send_message(self, username: str, message: str) -> bool:
        """Send message to specified user."""
        await self.client.send_message(username, message)
        return True

    @log_operation("get_dialog_messages")
    @handle_flood_wait("get_dialog_messages", sleep=True)
    @require_client(initialized=True)
    async def get_dialog_messages(self, username: str, limit: int = 100) -> list:
        """Get messages from dialog with user."""
        messages = []
        async for message in self.client.get_chat_history(username, limit=limit):
            messages.append(message)
        return messages

    # Status Operations
    @log_operation("check_flood_wait")
    @handle_flood_wait("check_flood_wait", return_time=True)
    @require_client(initialized=True)
    async def check_flood_wait(self) -> Optional[datetime]:
        """Check if account is in flood wait state."""
        if not self._initialized:
            return None

        await self.client.get_me()
        return None

    # Helper Methods
    async def _create_client(self) -> bool:
        """Create Pyrogram client instance."""
        try:
            logger.debug(f"Creating client instance for {self.phone}")
            self.client = Client(
                name=f"account_{self.phone}",
                api_id=API_ID,
                api_hash=API_HASH,
                session_string=self.session_string,
                phone_number=None if self.session_string else self.phone,
                in_memory=True,
            )
            return True
        except Exception as e:
            logger.error(f"Error creating client for {self.phone}: {e}", exc_info=True)
            return False

    async def _connect_client(self) -> bool:
        """Connect client to Telegram."""
        try:
            if self._connected:
                logger.debug(f"Client {self.phone} is already connected")
                return True

            logger.debug(f"Connecting client for {self.phone}")
            await self.client.connect()
            self._connected = True
            return True
        except Exception as e:
            logger.error(
                f"Error connecting client for {self.phone}: {e}", exc_info=True
            )
            return False

    async def _verify_session(self) -> bool:
        """Verify existing session."""
        try:
            me = await self.client.get_me()
            logger.debug(f"Successfully connected to account {me.phone_number}")
            return True
        except Exception as e:
            logger.error(f"Failed to verify session: {e}")
            await self.stop()
            return False

    async def _disconnect_client(self) -> None:
        """Disconnect client from Telegram."""
        if self._connected:
            logger.debug(f"Disconnecting client for {self.phone}")
            try:
                await self.client.disconnect()
            except Exception as e:
                if "already terminated" in str(e):
                    logger.debug(f"Client {self.phone} is already disconnected")
                else:
                    logger.error(f"Error disconnecting client: {e}")
            self._connected = False

    async def _terminate_client(self) -> None:
        """Terminate client instance."""
        if hasattr(self.client, "terminate"):
            logger.debug(f"Terminating client for {self.phone}")
            try:
                await self.client.terminate()
            except Exception as e:
                if "already terminated" in str(e):
                    logger.debug(f"Client {self.phone} is already terminated")
                else:
                    logger.error(f"Error terminating client: {e}")
