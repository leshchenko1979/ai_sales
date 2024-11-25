import asyncio
import logging
from typing import Optional, Tuple

from config import API_HASH, API_ID
from pyrogram import Client
from pyrogram.errors import (
    AuthKeyUnregistered,
    BadRequest,
    FloodWait,
    PasswordHashInvalid,
    PhoneCodeExpired,
    PhoneCodeInvalid,
    PhoneNumberInvalid,
    SessionPasswordNeeded,
)

from .models import Account, AccountStatus

logger = logging.getLogger(__name__)


class AccountClient:
    """
    Manages individual Telegram account connection and operations.
    Handles authentication, message sending, and connection management.
    """

    def __init__(self, account: Account):
        self.account = account
        self.client: Optional[Client] = None
        self._connect_retries = 3
        self._retry_delay = 5  # seconds
        self._phone_code_hash: Optional[str] = None
        self._exponential_backoff = True
        self._flood_wait_sleep = 1.1  # множитель для sleep при FloodWait

    async def __aenter__(self):
        """Support for async context manager"""
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Cleanup when used as context manager"""
        await self.disconnect()

    async def connect(self) -> bool:
        """
        Connect to Telegram with retry mechanism and exponential backoff.

        :return: True if connection successful
        """
        retry_count = 0
        current_delay = self._retry_delay

        while retry_count < self._connect_retries:
            try:
                if not self.client:
                    logger.debug(f"Initializing new client for {self.account.phone}")
                    self.client = Client(
                        name=f"account_{self.account.id}",
                        api_id=API_ID,
                        api_hash=API_HASH,
                        in_memory=True,
                        phone_number=self.account.phone,
                        session_string=self.account.session_string,
                    )

                if not self.client.is_connected:
                    await self.client.connect()

                if self.client.is_connected:
                    return True

                retry_count += 1
                if self._exponential_backoff:
                    current_delay *= 2
                await asyncio.sleep(current_delay)

            except AuthKeyUnregistered:
                logger.error(f"Session invalid for {self.account.phone}")
                self.account.session_string = None
                return False
            except Exception as e:
                logger.error(
                    f"Connection error for {self.account.phone}: {e}", exc_info=True
                )
                retry_count += 1
                if self._exponential_backoff:
                    current_delay *= 2
                await asyncio.sleep(current_delay)

        return False

    async def request_code(self) -> Tuple[bool, Optional[str]]:
        """
        Request authorization code from Telegram.

        :return: Tuple of (success, error_message)
        """
        if not self.client:
            return False, "Client not initialized"

        try:
            sent = await self.client.send_code(self.account.phone)
            if not sent or not sent.phone_code_hash:
                return False, "Failed to get phone code hash"

            self._phone_code_hash = sent.phone_code_hash
            self.account.request_code()
            return True, None

        except FloodWait as e:
            self.account.set_flood_wait(e.value)
            return False, f"FloodWait: {e.value} seconds"
        except PhoneNumberInvalid:
            return False, "Invalid phone number"
        except BadRequest as e:
            if "PHONE_NUMBER_BANNED" in str(e):
                self.account.status = AccountStatus.blocked
                return False, "Phone number is banned"
            return False, str(e)
        except Exception as e:
            return False, str(e)

    async def sign_in(
        self, code: str, password: Optional[str] = None
    ) -> Tuple[bool, Optional[str]]:
        """
        Sign in with the provided code and optional 2FA password.

        :param code: Authorization code
        :param password: Two-factor authentication password if needed
        :return: Tuple of (success, error_message)
        """
        try:
            if not self._phone_code_hash:
                return False, "No phone code hash available"

            try:
                signed_in = await self.client.sign_in(
                    phone_number=self.account.phone,
                    phone_code_hash=self._phone_code_hash,
                    phone_code=code,
                )

                # Handle successful sign in
                if signed_in:
                    session_string = await self.export_session_string()
                    if session_string:
                        self.account.activate(session_string)
                        return True, None
                    return False, "Failed to export session string"

                return False, "Sign in failed"

            except SessionPasswordNeeded:
                if not password:
                    self.account.status = AccountStatus.password_requested
                    return False, "Two-factor authentication required"

                try:
                    await self.client.check_password(password)
                    session_string = await self.export_session_string()
                    if session_string:
                        self.account.activate(session_string)
                        return True, None
                    return False, "Failed to export session string"
                except PasswordHashInvalid:
                    return False, "Invalid two-factor authentication password"

            except PhoneCodeInvalid:
                return False, "Invalid code"
            except PhoneCodeExpired:
                self.account.status = AccountStatus.new
                return False, "Code expired"

        except Exception as e:
            logger.error(f"Sign in error: {e}", exc_info=True)
            return False, str(e)

    async def export_session_string(self) -> Optional[str]:
        """Export session string after successful authorization"""
        try:
            return await self.client.export_session_string()
        except Exception as e:
            logger.error(f"Failed to export session string: {e}")
            return None

    async def send_message(self, username: str, text: str) -> bool:
        """
        Send message to user with safety checks and error handling.

        :param username: Target username
        :param text: Message text
        :return: True if message sent successfully
        """
        try:
            if not self.client or not self.account.can_be_used:
                return False

            if not await self._ensure_connection():
                return False

            # Используем цикл с обработкой FloodWait
            while True:
                try:
                    await self.client.send_message(username, text)
                    self.account.record_message()
                    return True
                except FloodWait as e:
                    logger.warning(
                        f"FloodWait: {e.value} seconds for {self.account.phone}"
                    )
                    self.account.set_flood_wait(e.value)
                    # Добавляем небольшой множитель к времени ожидания
                    await asyncio.sleep(e.value * self._flood_wait_sleep)
                    continue

        except Exception as e:
            logger.error(f"Failed to send message: {e}")
            return False

    async def _ensure_connection(self) -> bool:
        """
        Ensure client is connected, reconnect if needed.

        :return: True if connection is active
        """
        if not self.client.is_connected:
            return await self.connect()
        return True

    async def disconnect(self):
        """Disconnect client and cleanup resources"""
        if self.client:
            try:
                await self.client.disconnect()
            except Exception as e:
                logger.error(f"Error disconnecting client: {e}")
            finally:
                self.client = None
