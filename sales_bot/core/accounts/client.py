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

logger = logging.getLogger(__name__)


class AccountClient:
    """Telegram client for account operations."""

    def __init__(self, phone: str, session_string: Optional[str] = None):
        """Initialize client."""
        self.phone = phone
        self.session_string = session_string
        self.client: Optional[Client] = None

    async def start(self) -> bool:
        """Start client."""
        try:
            if self.session_string:
                # Use existing session
                self.client = Client(
                    name=f"account_{self.phone}",
                    api_id=API_ID,
                    api_hash=API_HASH,
                    session_string=self.session_string,
                    in_memory=True,
                )
            else:
                # Create new session
                self.client = Client(
                    name=f"account_{self.phone}",
                    api_id=API_ID,
                    api_hash=API_HASH,
                    phone_number=self.phone,
                    in_memory=True,
                )

            await self.client.start()
            return True

        except (AuthKeyDuplicated, AuthKeyUnregistered) as e:
            logger.warning(f"Invalid session for {self.phone}: {e}")
            return False

        except Exception as e:
            logger.error(f"Error starting client for {self.phone}: {e}", exc_info=True)
            return False

    async def stop(self):
        """Stop client."""
        if self.client:
            await self.client.stop()
            self.client = None

    async def send_code(self) -> bool:
        """Send authorization code."""
        try:
            if not self.client:
                return False

            await self.client.send_code(self.phone)
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
            if not self.client:
                return None

            # Try to sign in
            await self.client.sign_in(self.phone, code)

            # Get session string
            return await self.client.export_session_string()

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
            if not self.client:
                return None

            # Try to get me (lightweight request)
            await self.client.get_me()
            return None

        except FloodWait as e:
            # Return flood wait end time
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
