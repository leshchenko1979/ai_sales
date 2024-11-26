"""Test account authorization flow."""

import asyncio
import logging
import sys
from pathlib import Path
from typing import Optional

# Add root directory to PYTHONPATH
root_dir = Path(__file__).parent.parent
sys.path.append(str(root_dir))

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)

# Set DEBUG level for all loggers
for logger_name in [
    "core.accounts.client",
    "core.accounts.manager",
    "core.accounts.monitoring",
    "pyrogram",
]:
    logging.getLogger(logger_name).setLevel(logging.DEBUG)

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


async def test_account_flow(phone: Optional[str] = None) -> bool:
    """
    Full account lifecycle test:
    1. Create account
    2. Request authorization code
    3. Authorize
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

        from core.accounts.manager import AccountManager
        from core.accounts.models import AccountStatus
        from core.accounts.monitoring import AccountMonitor
        from core.db import get_db
        from infrastructure.logging import setup_logging

        # Initialize logging
        setup_logging()

        # Initialize database
        await get_db()

        # Initialize managers
        manager = AccountManager()
        monitor = AccountMonitor()

        # Use test number if not specified
        phone = phone or "79306974071"
        logger.info(f"Testing account {phone}")

        # 1. Create account
        logger.info("1. Creating account...")
        account = await manager.get_or_create_account(phone)
        assert account is not None, "Failed to create account"
        assert account.phone == phone, f"Wrong phone number: {account.phone}"
        logger.info(f"Created account {account}")

        # 2. Request authorization code
        if account.status == AccountStatus.new:
            logger.info("2. Requesting authorization code...")
            code_requested = await manager.request_code(phone)
            assert code_requested, "Failed to request code"

            # Get fresh data
            account = await manager.get_or_create_account(phone)
            assert (
                account.status == AccountStatus.code_requested
            ), f"Wrong status: {account.status}"

            # 3. Authorization
            logger.info("3. Authorizing account...")
            code = input("Enter authorization code: ").strip()
            authorized = await manager.authorize_account(phone, code)
            assert authorized, "Failed to authorize account"

        # 4. Check status
        logger.info("4. Checking status...")
        account = await manager.get_or_create_account(phone)
        assert account.status == AccountStatus.active, f"Wrong status: {account.status}"
        assert account.session_string is not None, "Missing session_string"

        # 5. Check flood wait
        logger.info("5. Checking flood wait...")
        assert not account.is_in_flood_wait, "Account should not be in flood wait"
        assert account.can_be_used, "Account should be usable"

        # 6. Check monitoring
        logger.info("6. Checking monitoring...")
        stats = await monitor.check_accounts()
        assert stats is not None, "Failed to get monitoring stats"
        assert stats.total > 0, "No accounts found"
        assert stats.active > 0, "No active accounts"

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
