"""Script to check accounts in database."""

import asyncio
import sys
from pathlib import Path

from dotenv import load_dotenv

# Add project root to path
root_dir = Path(__file__).parent.parent
sys.path.append(str(root_dir))

load_dotenv()

from core.accounts.models import AccountStatus
from core.accounts.queries import AccountQueries
from core.db import get_db, with_queries


@with_queries(AccountQueries)
async def check_accounts(queries: AccountQueries):
    """Check all accounts in database."""
    async with get_db():
        # Get all accounts
        print("\nAll accounts in database:")
        print("-" * 100)
        print(
            f"{'ID':<5} {'Phone':<15} {'Status':<10} {'Has Session':<12} {'Messages':<10} {'Can Be Used'}"
        )
        print("-" * 100)

        accounts = await queries.get_all_accounts()
        for account in accounts:
            # Check if account can be used
            can_be_used = (
                account.status == AccountStatus.active
                and account.session_string is not None
                and (account.daily_messages or 0) < 40
            )

            print(
                f"{account.id:<5} "
                f"{account.phone:<15} "
                f"{account.status.value:<10} "
                f"{'Yes' if account.session_string else 'No':<12} "
                f"{account.daily_messages or 0:<10} "
                f"{'Yes' if can_be_used else 'No'}"
            )
        print("-" * 100)
        print(f"Total accounts: {len(accounts)}")

        # Get active accounts
        active_accounts = await queries.get_active_accounts()
        print(f"\nActive accounts: {len(active_accounts)}")

        # Check why accounts are not available
        if active_accounts:
            print("\nActive accounts status:")
            for acc in active_accounts:
                reasons = []
                if acc.session_string is None:
                    reasons.append("No session string")
                if (acc.daily_messages or 0) >= 40:
                    reasons.append("Daily message limit reached")
                status = (
                    "Available"
                    if not reasons
                    else f"Not available: {', '.join(reasons)}"
                )
                print(f"- {acc.phone}: {status}")
        else:
            print("No active accounts found in database")


if __name__ == "__main__":
    asyncio.run(check_accounts())
