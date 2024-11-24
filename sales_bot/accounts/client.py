import logging
from pyrogram import Client
from typing import Optional

from sales_bot.config import API_ID, API_HASH
from .models import Account

logger = logging.getLogger(__name__)

class AccountClient:
    def __init__(self, account: Account):
        self.account = account
        self.client: Optional[Client] = None

    async def connect(self) -> bool:
        """Connect to Telegram using account credentials"""
        try:
            # Create client with session string if exists, or create new
            self.client = Client(
                name=f"account_{self.account.id}",
                api_id=API_ID,
                api_hash=API_HASH,
                session_string=self.account.session_string,
                in_memory=True
            )

            await self.client.start()
            return True

        except Exception as e:
            logger.error(f"Failed to connect account {self.account.phone}: {e}")
            return False

    async def authorize(self, code: str) -> Optional[str]:
        """
        Authorize account with received code
        Returns session string if successful
        """
        try:
            # Sign in with phone and code
            await self.client.sign_in(self.account.phone, code)

            # Export session string
            return await self.client.export_session_string()

        except Exception as e:
            logger.error(f"Failed to authorize account {self.account.phone}: {e}")
            return None

    async def send_message(self, username: str, text: str) -> bool:
        """Send message to user"""
        try:
            await self.client.send_message(username, text)
            return True
        except Exception as e:
            logger.error(f"Failed to send message from {self.account.phone} to {username}: {e}")
            return False

    async def disconnect(self):
        """Disconnect client"""
        if self.client:
            await self.client.stop()
