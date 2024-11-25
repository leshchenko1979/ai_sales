import logging
from typing import Optional

from config import API_HASH, API_ID
from pyrogram import Client
from pyrogram.errors import BadRequest, FloodWait, PhoneCodeExpired, PhoneCodeInvalid

from .models import Account, AccountStatus

logger = logging.getLogger(__name__)


class AccountClient:
    def __init__(self, account: Account):
        self.account = account
        self.client: Optional[Client] = None
        self._connect_retries = 3
        self._retry_delay = 5  # seconds
        self._phone_code_hash: Optional[str] = None

    async def connect(self) -> bool:
        """Connect to Telegram"""
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
                logger.debug(f"Client initialized with API ID: {API_ID}")

            if not self.client.is_connected:
                logger.debug(f"Attempting to connect client for {self.account.phone}")
                await self.client.connect()

            if not self.client.is_connected:
                logger.error(f"Failed to connect client for {self.account.phone}")
                return False

            # For new accounts or those without session string, always request code
            if not self.account.session_string:
                logger.debug(f"Attempting to send code to {self.account.phone}")
                try:
                    # Try to send code
                    sent = await self.client.send_code(self.account.phone)
                    logger.debug(f"Send code response: {vars(sent)}")

                    if not sent or not sent.phone_code_hash:
                        logger.error(
                            f"Failed to get phone code hash for {self.account.phone}"
                        )
                        return False

                    self._phone_code_hash = sent.phone_code_hash
                    logger.info(
                        f"Received phone code hash: {self._phone_code_hash[:5]}..."
                    )

                    # Log code delivery details
                    logger.debug(f"Code delivery details for {self.account.phone}:")
                    logger.debug(f"- Code type: {sent.type}")
                    logger.debug(f"- Next type: {sent.next_type}")
                    logger.debug(f"- Timeout: {sent.timeout}")

                    # Update account status
                    self.account.request_code()
                    logger.debug(f"Updated account status to {self.account.status}")

                    return True

                except FloodWait:
                    logger.error(
                        f"FloodWait error for {self.account.phone}. "
                        "Need to wait {e.value} seconds"
                    )
                    return False
                except BadRequest as e:
                    if "PHONE_NUMBER_BANNED" in str(e):
                        logger.error(
                            f"Phone number {self.account.phone} is banned by Telegram"
                        )
                    elif "API_ID_INVALID" in str(e):
                        logger.error("Invalid API ID. Check your API credentials")
                    elif "API_ID_PUBLISHED_FLOOD" in str(e):
                        logger.error("Too many requests with this API ID. Need to wait")
                    else:
                        logger.error(
                            f"Bad request error for {self.account.phone}: {str(e)}"
                        )
                    return False
                except Exception as e:
                    logger.error(
                        f"Error sending code to {self.account.phone}: {str(e)}",
                        exc_info=True,
                    )
                    return False

            return True

        except Exception as e:
            logger.error(
                f"Connection error for {self.account.phone}: {e}", exc_info=True
            )
            return False

    async def authorize(self, code: str) -> Optional[str]:
        """Authorize account with received code"""
        try:
            if not self.client:
                logger.error("Client not initialized")
                return None

            if not self._phone_code_hash:
                logger.error(
                    "No phone code hash available. Did you request a code first?"
                )
                return None

            logger.info(f"Starting authorization for account {self.account.phone}")

            try:
                logger.info(f"Attempting to sign in with code for {self.account.phone}")
                signed_in = await self.client.sign_in(
                    phone_number=self.account.phone,
                    phone_code_hash=self._phone_code_hash,
                    phone_code=code,
                )
                logger.info(
                    f"Sign in result for {self.account.phone}: {type(signed_in)}"
                )

                # Handle 2FA if needed
                if isinstance(signed_in, bool) and not signed_in:
                    logger.error(f"Failed to sign in account {self.account.phone}")
                    self.account.status = AccountStatus.new
                    return None

                # Export session string
                logger.info(f"Exporting session string for {self.account.phone}")
                session_string = await self.client.export_session_string()
                if self.account.activate(session_string):
                    logger.info(f"Successfully activated account {self.account.phone}")
                    return session_string

                logger.error(f"Failed to activate account {self.account.phone}")
                return None

            except PhoneCodeInvalid:
                logger.error(f"Invalid code provided for account {self.account.phone}")
                return None
            except PhoneCodeExpired:
                logger.error(f"Code expired for account {self.account.phone}")
                self.account.status = AccountStatus.new
                return None
            except Exception as e:
                logger.error(
                    f"Error during sign in for {self.account.phone}: {str(e)}",
                    exc_info=True,
                )
                return None

        except Exception as e:
            logger.error(
                f"Authorization failed for {self.account.phone}: {str(e)}",
                exc_info=True,
            )
            return None

    async def sign_in(self, code: str) -> bool:
        """Sign in with the provided code using stored phone code hash"""
        try:
            logger.info(f"Starting authorization for account {self.account.phone}")
            if not self._phone_code_hash:
                logger.error(f"No phone code hash available for {self.account.phone}")
                return False

            await self.client.sign_in(
                phone_number=self.account.phone,
                phone_code_hash=self._phone_code_hash,
                phone_code=code,
            )
            return True

        except Exception:
            logger.error(f"Invalid code provided for account {self.account.phone}")
            return False

    async def export_session_string(self) -> Optional[str]:
        """Export session string after successful authorization"""
        try:
            return await self.client.export_session_string()
        except Exception as e:
            logger.error(
                f"Failed to export session string for {self.account.phone}: {e}"
            )
            return None

    async def send_message(self, username: str, text: str) -> bool:
        """Send message to user"""
        try:
            if not self.client or not self.account.can_be_used:
                return False

            await self.client.send_message(username, text)
            self.account.record_message()
            return True

        except FloodWait as e:
            logger.warning(
                f"Got FloodWait for {e.value} seconds "
                "while sending message from {self.account.phone}"
            )
            self.account.set_flood_wait(e.value)
            raise

        except Exception as e:
            logger.error(f"Failed to send message: {e}")
            return False

    async def disconnect(self):
        """Disconnect client"""
        if self.client:
            await self.client.disconnect()
            self.client = None
