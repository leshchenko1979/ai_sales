"""Telegram client for account operations."""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Optional

from infrastructure.config import API_HASH, API_ID
from pyrogram import Client
from pyrogram.errors import (
    AuthKeyDuplicated,
    AuthKeyUnregistered,
    FloodWait,
    SessionPasswordNeeded,
)
from utils.phone import normalize_phone

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

    async def start(self, check_auth: bool = True) -> bool:
        """
        Start client.

        Args:
            check_auth: If True, verify authorization status.
                      If False, just create and connect client without checking auth.
        """
        try:
            if self._initialized and self.client:
                return True

            logger.debug(f"Starting client for {self.phone} (check_auth={check_auth})")

            # Create client instance
            if not await self._create_client():
                return False

            # Connect to Telegram
            if not await self._connect_client():
                return False

            if not check_auth:
                logger.debug(f"Skipping auth check for {self.phone}")
                self._initialized = True
                return True

            # Verify session if exists
            if self.session_string:
                try:
                    me = await self.client.get_me()
                    logger.debug(f"Successfully connected to account {me.phone_number}")
                except Exception as e:
                    logger.error(f"Failed to verify session: {e}")
                    await self.stop()
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

    async def stop(self):
        """Stop client."""
        if not self.client:
            logger.debug(f"No client instance for {self.phone}")
            return

        try:
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

            if hasattr(self.client, "terminate"):
                logger.debug(f"Terminating client for {self.phone}")
                try:
                    await self.client.terminate()
                except Exception as e:
                    if "already terminated" in str(e):
                        logger.debug(f"Client {self.phone} is already terminated")
                    else:
                        logger.error(f"Error terminating client: {e}")

        except Exception as e:
            logger.error(f"Error stopping client for {self.phone}: {e}")
        finally:
            self.client = None
            self._initialized = False
            self._connected = False

    async def send_code(self) -> bool:
        """Send authorization code."""
        try:
            if not self.client:
                logger.error("Client not initialized")
                return False

            # Make sure client is connected
            if not await self._connect_client():
                return False

            # Send code
            sent = await self.client.send_code(self.phone)
            self.phone_code_hash = sent.phone_code_hash
            logger.debug(f"Sent code to {self.phone}")
            return True

        except FloodWait as e:
            logger.warning(f"FloodWait for {self.phone}: {e.value} seconds")
            return False

        except Exception as e:
            logger.error(f"Error sending code to {self.phone}: {e}", exc_info=True)
            return False

    async def sign_in(self, code: str) -> Optional[str]:
        """Sign in with code."""
        try:
            if not self.client or not self._initialized:
                return None

            # Try to sign in
            await self.client.sign_in(
                phone_number=self.phone,
                phone_code_hash=self.phone_code_hash,
                phone_code=code,
            )

            # Get session string
            session_string = await self.client.export_session_string()
            self.session_string = session_string
            return session_string

        except SessionPasswordNeeded:
            logger.warning(f"2FA password required for {self.phone}")
            return None

        except FloodWait as e:
            logger.warning(f"FloodWait for {self.phone}: {e.value} seconds")
            return None

        except Exception as e:
            logger.error(f"Error signing in {self.phone}: {e}", exc_info=True)
            return None

    async def check_flood_wait(self) -> Optional[datetime]:
        """Check if account is in flood wait."""
        try:
            if not self.client or not self._initialized:
                return None

            # Try to get me (lightweight request)
            await self.client.get_me()
            return None

        except FloodWait as e:
            # Return flood wait end time in UTC
            return datetime.utcnow() + timedelta(seconds=e.value)

        except Exception as e:
            logger.error(
                f"Error checking flood wait for {self.phone}: {e}", exc_info=True
            )
            return None

    async def send_message(self, username: str, message: str) -> bool:
        """Send message to user."""
        try:
            if not self.client:
                return False

            # Send message
            await self.client.send_message(username, message)
            return True

        except FloodWait as e:
            logger.warning(f"FloodWait for {self.phone}: {e.value} seconds")
            return False

        except Exception as e:
            logger.error(
                f"Error sending message from {self.phone} to {username}: {e}",
                exc_info=True,
            )
            return False

    async def get_dialog_messages(self, username: str, limit: int = 100) -> list:
        """Get messages from dialog."""
        try:
            if not self.client:
                return []

            # Get messages
            messages = []
            async for message in self.client.get_chat_history(username, limit=limit):
                messages.append(message)
            return messages

        except FloodWait as e:
            logger.warning(f"FloodWait for {self.phone}: {e.value} seconds")
            await asyncio.sleep(e.value)
            return []

        except Exception as e:
            logger.error(
                f"Error getting messages from {self.phone} with {username}: {e}",
                exc_info=True,
            )
            return []
