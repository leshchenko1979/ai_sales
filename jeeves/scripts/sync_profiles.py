"""Script to sync profiles from Telegram."""

import asyncio
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict

from dotenv import load_dotenv

# Add project root to path
root_dir = Path(__file__).parent.parent
sys.path.append(str(root_dir))

load_dotenv()

from core.accounts import AccountManager
from core.accounts.models import Account, AccountStatus
from core.accounts.queries.account import AccountQueries
from core.db import with_queries

logger = logging.getLogger(__name__)

# Maximum number of concurrent sync operations
MAX_CONCURRENT_SYNCS = 5


async def sync_single_profile(
    account: Account,
    manager: AccountManager,
) -> Dict:
    """Sync single account profile."""
    result = {
        "success": False,
        "error": None,
        "start_time": datetime.now(),
        "end_time": None,
    }

    try:
        logger.debug(f"Starting sync for account {account.phone}")

        # Skip accounts without session
        if not account.session_string:
            result["error"] = "No session string"
            return result

        # Skip non-active accounts
        if account.status != AccountStatus.active:
            result["error"] = f"Account not active (status: {account.status})"
            return result

        # Sync profile using manager
        if await manager.sync_account_profile(account.phone):
            result["success"] = True
        else:
            result["error"] = "Failed to sync profile"

    except Exception as e:
        logger.error(
            f"Error syncing profile for account {account.phone}: {e}", exc_info=True
        )
        result["error"] = str(e)

    finally:
        result["end_time"] = datetime.now()
        duration = result["end_time"] - result["start_time"]
        status = "✅" if result["success"] else "❌"
        logger.info(
            f"{status} Account {account.phone} sync completed in {duration.total_seconds():.1f}s"
            + (f" (Error: {result['error']})" if result["error"] else "")
        )

    return result


@with_queries((AccountQueries))
async def sync_profiles(queries: AccountQueries):
    """Sync all profiles from Telegram."""
    start_time = datetime.now()
    stats = {
        "total": 0,
        "success": 0,
        "failed": 0,
        "skipped": 0,
    }

    try:
        # Get all active accounts
        accounts = await queries.get_active_accounts()
        if not accounts:
            logger.info("No active accounts found")
            return

        stats["total"] = len(accounts)
        logger.info(f"Starting sync for {len(accounts)} accounts")

        # Create account manager
        manager = AccountManager()

        # Create sync tasks
        tasks = []
        semaphore = asyncio.Semaphore(MAX_CONCURRENT_SYNCS)

        async def sync_with_semaphore(account: Account):
            async with semaphore:
                return await sync_single_profile(account, manager)

        # Start all sync tasks
        for account in accounts:
            tasks.append(sync_with_semaphore(account))

        # Wait for all tasks to complete
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Process results
        for result in results:
            if isinstance(result, Exception):
                stats["failed"] += 1
                continue

            if result["success"]:
                stats["success"] += 1
            elif result["error"] in ["No session string", "Account not active"]:
                stats["skipped"] += 1
            else:
                stats["failed"] += 1

    except Exception as e:
        logger.error(f"Error syncing profiles: {e}", exc_info=True)
        raise

    finally:
        # Log final statistics
        duration = datetime.now() - start_time
        logger.info(
            f"\nSync completed in {duration.total_seconds():.1f}s:\n"
            f"Total accounts: {stats['total']}\n"
            f"✅ Successful: {stats['success']}\n"
            f"⏭️ Skipped: {stats['skipped']}\n"
            f"❌ Failed: {stats['failed']}"
        )


if __name__ == "__main__":
    # Setup logging
    from infrastructure.logging import setup_logging

    setup_logging()

    # Run sync
    asyncio.run(sync_profiles())
