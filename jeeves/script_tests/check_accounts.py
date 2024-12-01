"""Script to check accounts in database."""

# Standard library
import asyncio
import sys
from pathlib import Path
from typing import List

# Third-party imports
from dotenv import load_dotenv

# Setup path
root_dir = Path(__file__).parent.parent
sys.path.append(str(root_dir))

# Environment setup
load_dotenv()

# Local imports
from core.accounts.models import AccountStatus
from core.accounts.queries import AccountQueries
from core.db import get_db, with_queries


class AccountChecker:
    """Account status checker."""

    def __init__(self):
        """Initialize checker."""
        self.separator = "-" * 100

    def print_header(self):
        """Print table header."""
        print("\nAll accounts in database:")
        print(self.separator)
        print(
            f"{'ID':<5} {'Phone':<15} {'Status':<10} {'Has Session':<12} "
            f"{'Messages':<10} Can Be Used"
        )
        print(self.separator)

    def print_account_info(self, account) -> None:
        """Print single account information."""
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

    def print_active_status(self, account) -> None:
        """Print active account status."""
        reasons = []
        if account.session_string is None:
            reasons.append("No session string")
        if (account.daily_messages or 0) >= 40:
            reasons.append("Daily message limit reached")

        status = f"Not available: {', '.join(reasons)}" if reasons else "Available"
        print(f"- {account.phone}: {status}")

    @with_queries(AccountQueries)
    async def check_accounts(self, queries: AccountQueries):
        """Check all accounts in database."""
        async with get_db():
            # Get and display all accounts
            accounts = await queries.get_all_accounts()
            self.display_all_accounts(accounts)

            # Get and display active accounts
            active_accounts = await queries.get_active_accounts()
            self.display_active_accounts(active_accounts)

    def display_all_accounts(self, accounts: List) -> None:
        """Display information about all accounts."""
        self.print_header()
        for account in accounts:
            self.print_account_info(account)
        print(self.separator)
        print(f"Total accounts: {len(accounts)}")

    def display_active_accounts(self, active_accounts: List) -> None:
        """Display information about active accounts."""
        print(f"\nActive accounts: {len(active_accounts)}")

        if not active_accounts:
            print("No active accounts found in database")
            return

        print("\nActive accounts status:")
        for account in active_accounts:
            self.print_active_status(account)


def main():
    """Main entry point."""
    checker = AccountChecker()
    asyncio.run(checker.check_accounts())
