"""Account authorization script."""

import asyncio
import sys
from pathlib import Path
from typing import Optional

from core.accounts.client import AccountClient
from core.accounts.models.account import AccountStatus
from infrastructure import logging

ROOT_DIR = Path(__file__).parent.parent
sys.path.append(str(ROOT_DIR))

from core.accounts import AccountManager
from core.accounts.monitor import AccountMonitor


class AccountAuthorizer:
    """Account authorization handler."""

    def __init__(self):
        """Initialize authorizer."""
        self.logger = logging.getLogger(__name__)
        self.manager = AccountManager()
        self.monitor = AccountMonitor()

    async def request_authorization_code(self, phone: str) -> bool:
        """Request authorization code from Telegram."""
        self.logger.debug(f"Starting authorization flow for phone {phone}")

        # Request code
        self.logger.debug("Requesting authorization code...")
        if not await self.manager.request_code(phone):
            self.logger.error("Failed to request authorization code")
            return False

        self.logger.debug("Authorization code requested successfully")
        return True

    def get_confirmation_code(self) -> str:
        """Get confirmation code from user input."""
        print("\nThe confirmation code has been sent via Telegram app")
        self.logger.debug("Waiting for user to input confirmation code...")

        while True:
            code = input("Enter confirmation code: ").strip()

            if not code:
                self.logger.warning("Empty code entered, please try again")
                continue

            if not code.isdigit():
                self.logger.warning("Code must contain only digits, please try again")
                continue

            if len(code) < 5:
                self.logger.warning("Code is too short, please try again")
                continue

            break

        self.logger.debug(f"Received confirmation code of length {len(code)}")
        return code

    async def authorize_with_code(self, phone: str, code: str) -> bool:
        """Authorize account with confirmation code."""
        self.logger.debug("Attempting to authorize account...")

        if not await self.manager.authorize_account(phone, code):
            self.logger.error("Failed to authorize account")
            return False

        final_account = await self.manager.get_or_create_account(phone)
        self.logger.debug(f"Final account status: {final_account.status}")
        self.logger.debug("Authorization completed successfully")

        return True

    async def verify_existing_session(self, phone: str, session_string: str) -> bool:
        """Verify existing session is valid."""
        self.logger.info("Account is already active, verifying session...")
        client = AccountClient(phone, session_string)

        if not await client.start():
            self.logger.error("Failed to connect with existing session")
            return False

        self.logger.info("Successfully connected with existing session")
        await client.stop()
        return True

    async def run_authorization_flow(self, phone: str) -> bool:
        """Run complete authorization flow."""
        try:
            # Request code
            if not await self.request_authorization_code(phone):
                return False

            # Get account status
            account = await self.manager.get_or_create_account(phone)
            self.logger.debug(f"Current account status: {account.status}")

            # Get and verify code
            code = self.get_confirmation_code()
            return await self.authorize_with_code(phone, code)

        except Exception as e:
            self.logger.error(f"Authorization error: {e}", exc_info=True)
            return False

    async def test_account(self, phone: Optional[str] = None) -> bool:
        """Test complete account lifecycle."""
        try:
            phone = phone or "79189452071"
            self.logger.info(f"Testing account {phone}")

            # Create/get account
            self.logger.info("1. Creating account...")
            account = await self.manager.get_or_create_account(phone)
            if not account or account.phone != phone:
                self.logger.error("Failed to create/get account")
                return False

            # Handle authorization
            if account.status != AccountStatus.active:
                self.logger.info("2. Starting authorization flow...")
                if not await self.run_authorization_flow(phone):
                    return False
            elif not await self.verify_existing_session(phone, account.session_string):
                return False

            # Verify final state
            await self.verify_account_state(phone)
            self.logger.info("✅ All tests passed successfully!")
            return True

        except Exception as e:
            self.logger.error(f"❌ Test failed: {e}", exc_info=True)
            return False

        finally:
            await asyncio.sleep(1)  # Wait for pending tasks

    async def verify_account_state(self, phone: str) -> None:
        """Verify account is in correct state."""
        # Check status
        self.logger.info("3. Checking status...")
        account = await self.manager.get_or_create_account(phone)
        assert account.status == AccountStatus.active, f"Wrong status: {account.status}"
        assert account.session_string is not None, "Missing session_string"

        # Check flood wait
        self.logger.info("4. Checking flood wait...")
        assert not account.is_in_flood_wait, "Account should not be in flood wait"
        assert account.can_be_used, "Account should be usable"

        # Check monitoring
        self.logger.info("5. Checking monitoring...")
        stats = await self.monitor.check_accounts()
        assert stats is not None, "Failed to get monitoring stats"
        assert stats["total"] > 0, "No accounts found"
        assert stats["active"] > 0, "No active accounts"


def setup_pyrogram_logging():
    """Configure Pyrogram logging."""
    pyrogram_loggers = [
        "pyrogram",
        "pyrogram.client",
        "pyrogram.session.session",
        "pyrogram.session.auth",
        "pyrogram.session.connection",
        "pyrogram.crypto",
    ]
    for logger_name in pyrogram_loggers:
        logging.getLogger(logger_name).setLevel(logging.ERROR)


def main():
    """Main entry point."""
    try:
        # Setup logging
        logging.setup_logging()
        setup_pyrogram_logging()

        # Run test
        authorizer = AccountAuthorizer()
        success = asyncio.run(authorizer.test_account())
        sys.exit(0 if success else 1)

    except KeyboardInterrupt:
        logging.getLogger(__name__).info("Test interrupted by user")
        sys.exit(1)
    except Exception as e:
        logging.getLogger(__name__).critical(f"Unexpected error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
