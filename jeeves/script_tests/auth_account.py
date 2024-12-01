"""Test account authorization flow."""

import asyncio
import logging
import sys
from pathlib import Path
from typing import Optional

# Add root directory to PYTHONPATH
root_dir = Path(__file__).parent.parent
sys.path.append(str(root_dir))

# Create console handler with formatting
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setLevel(logging.DEBUG)
formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
console_handler.setFormatter(formatter)

# Configure root logger
root_logger = logging.getLogger()
root_logger.setLevel(logging.DEBUG)
root_logger.addHandler(console_handler)

# Mute all Pyrogram logs except critical
for logger_name in [
    "pyrogram",
    "pyrogram.client",
    "pyrogram.session.session",
    "pyrogram.session.auth",
    "pyrogram.session.connection",
    "pyrogram.crypto",
]:
    logging.getLogger(logger_name).setLevel(logging.ERROR)

# Configure specific loggers
loggers = [
    "__main__",
    "core.accounts.client",
    "core.accounts.manager",
    "core.accounts.monitoring",
    "core.accounts.client_manager",
    "core.accounts.queries",
    "core.db",
]

# Configure each logger
for logger_name in loggers:
    logger = logging.getLogger(logger_name)
    logger.setLevel(logging.DEBUG)
    # Remove any existing handlers
    logger.handlers = []
    # Add console handler
    logger.addHandler(console_handler)
    # Don't propagate to avoid duplicate logs
    logger.propagate = False

# Get logger for this module
logger = logging.getLogger(__name__)
logger.debug("Logger initialized with DEBUG level")


async def authorize_account(phone: str, manager) -> bool:
    """Handle account authorization flow."""
    try:
        logger.debug(f"Starting authorization flow for phone {phone}")

        # Request authorization code
        logger.debug("Requesting authorization code...")
        code_requested = await manager.request_code(phone)
        if not code_requested:
            logger.error("Failed to request authorization code")
            return False
        logger.debug("Authorization code requested successfully")

        # Get fresh account data to verify status
        logger.debug("Getting fresh account data...")
        account = await manager.get_or_create_account(phone)
        logger.debug(f"Current account status: {account.status}")

        # Get code from user (without using Pyrogram's input)
        print("\nThe confirmation code has been sent via Telegram app")
        logger.debug("Waiting for user to input confirmation code...")

        while True:
            code = input("Enter confirmation code: ").strip()
            if not code:
                logger.warning("Empty code entered, please try again")
                continue
            if not code.isdigit():
                logger.warning("Code must contain only digits, please try again")
                continue
            if len(code) < 5:
                logger.warning("Code is too short, please try again")
                continue
            break

        logger.debug(f"Received confirmation code of length {len(code)}")

        # Authorize account
        logger.debug("Attempting to authorize account...")
        authorized = await manager.authorize_account(phone, code)
        if not authorized:
            logger.error("Failed to authorize account")
            return False

        # Get final account state
        final_account = await manager.get_or_create_account(phone)
        logger.debug(f"Final account status: {final_account.status}")
        logger.debug("Authorization completed successfully")

        return True

    except Exception as e:
        logger.error(f"Authorization error: {e}", exc_info=True)
        return False


async def test_account_flow(phone: Optional[str] = None) -> bool:
    """
    Full account lifecycle test:
    1. Create account
    2. Request authorization code (only if not active)
    3. Authorize (only if not active)
    4. Check status
    5. Check flood wait
    6. Check monitoring

    Args:
        phone: Phone number for testing. If None, test number is used.

    Returns:
        bool: True if all tests passed successfully
    """
    try:
        from dotenv import load_dotenv

        load_dotenv()

        from core.accounts.client import AccountClient
        from core.accounts.manager import AccountManager
        from core.accounts.models.account import AccountStatus
        from core.accounts.monitoring import AccountMonitor
        from infrastructure.logging import setup_logging

        # Initialize logging
        setup_logging()

        # Initialize managers
        manager = AccountManager()
        monitor = AccountMonitor()

        # Use test number if not specified
        phone = phone or "79189452071"
        logger.info(f"Testing account {phone}")

        # 1. Create account
        logger.info("1. Creating account...")
        account = await manager.get_or_create_account(phone)
        assert account is not None, "Failed to create account"
        assert account.phone == phone, f"Wrong phone number: {account.phone}"
        logger.info(f"Created account {account}")

        # 2. Authorization flow if not active
        if account.status != AccountStatus.active:
            logger.info("2. Starting authorization flow...")
            authorized = await authorize_account(phone, manager)
            assert authorized, "Authorization failed"
        else:
            logger.info("Account is already active, verifying session...")
            client = AccountClient(phone, account.session_string)
            assert await client.start(), "Failed to connect with existing session"
            logger.info("Successfully connected with existing session")
            await client.stop()

        # 3. Check status
        logger.info("3. Checking status...")
        account = await manager.get_or_create_account(phone)
        assert account.status == AccountStatus.active, f"Wrong status: {account.status}"
        assert account.session_string is not None, "Missing session_string"

        # 4. Check flood wait
        logger.info("4. Checking flood wait...")
        assert not account.is_in_flood_wait, "Account should not be in flood wait"
        assert account.can_be_used, "Account should be usable"

        # 5. Check monitoring
        logger.info("5. Checking monitoring...")
        stats = await monitor.check_accounts()
        assert stats is not None, "Failed to get monitoring stats"
        assert stats["total"] > 0, "No accounts found"
        assert stats["active"] > 0, "No active accounts"

        logger.info("✅ All tests passed successfully!")
        return True

    except Exception as e:
        logger.error(f"❌ Test failed: {e}", exc_info=True)
        return False

    finally:
        # Clean up
        await asyncio.sleep(1)  # Wait for any pending tasks


if __name__ == "__main__":
    try:
        # Run test
        success = asyncio.run(test_account_flow())
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        logger.info("Test interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.critical(f"Unexpected error: {e}", exc_info=True)
        sys.exit(1)
