import asyncio
import logging
from typing import Optional

from config import API_HASH, API_ID
from pyrogram import Client
from pyrogram.errors import AuthKeyUnregistered, SessionPasswordNeeded

from .models import Account

logger = logging.getLogger(__name__)


class AccountClient:
    def __init__(self, account: Account):
        self.account = account
        self.client: Optional[Client] = None
        self._connect_retries = 3
        self._retry_delay = 5  # seconds

    async def connect(self) -> bool:
        """Connect to Telegram using account credentials"""
        for attempt in range(self._connect_retries):
            try:
                self.client = Client(
                    name=f"account_{self.account.id}",
                    api_id=API_ID,
                    api_hash=API_HASH,
                    session_string=self.account.session_string or None,
                    in_memory=True,
                    device_model="iPhone 13",
                    system_version="iOS 15.0",
                    app_version="Telegram iOS 8.0",
                )

                await self.client.start()
                return True

            except AuthKeyUnregistered:
                logger.error(
                    f"Session invalid for account {self.account.phone}, "
                    "needs reauthorization"
                )
                return False

            except Exception as e:
                logger.warning(
                    f"Connection attempt {attempt + 1} failed "
                    f"for account {self.account.phone}: {e}"
                )
                if attempt < self._connect_retries - 1:
                    await asyncio.sleep(self._retry_delay)
                continue

        logger.error(
            f"Failed to connect account {self.account.phone} "
            f"after {self._connect_retries} attempts"
        )
        return False

    async def authorize(self, code: str) -> Optional[str]:
        """Authorize account with received code"""
        try:
            # Sign in with phone and code
            signed_in = await self.client.sign_in(self.account.phone, code)

            # Handle 2FA if needed
            if isinstance(signed_in, bool) and not signed_in:
                logger.error(f"Failed to sign in account {self.account.phone}")
                return None

            # Export session string
            return await self.client.export_session_string()

        except SessionPasswordNeeded:
            logger.error(f"2FA required for account {self.account.phone}")
            return None

        except Exception as e:
            logger.error(f"Failed to authorize account {self.account.phone}: {e}")
            return None

    async def send_message(self, username: str, text: str) -> bool:
        """Send message to user"""
        try:
            await self.client.send_message(username, text)
            return True
        except Exception as e:
            logger.error(
                f"Failed to send message from {self.account.phone} to {username}: {e}"
            )
            return False

    async def disconnect(self):
        """Disconnect client"""
        if self.client and self.client.is_connected:
            try:
                await self.client.stop()
            except ConnectionError as e:
                logger.debug(f"Client already disconnected: {e}")
            except Exception as e:
                logger.error(f"Error disconnecting client: {e}")
        self.client = None
