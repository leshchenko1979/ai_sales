"""Script to check account profiles in database."""

# Standard library
import asyncio
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, List, Optional, Tuple

# Third-party imports
from dotenv import load_dotenv
from sqlalchemy.orm import selectinload

# Setup path
root_dir = Path(__file__).parent.parent
sys.path.append(str(root_dir))

# Environment setup
load_dotenv()

# Local imports
from core.accounts.models import AccountProfile
from core.accounts.queries import AccountQueries, ProfileQueries
from core.db import with_queries


class TextFormatter:
    """Text formatting utilities."""

    @staticmethod
    def format_datetime(dt: Optional[datetime]) -> str:
        """Format datetime for display in a human-readable format."""
        if not dt:
            return "Never"

        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)

        delta = datetime.now(timezone.utc) - dt

        if delta.days > 0:
            return f"{delta.days}d ago"
        if (hours := delta.seconds // 3600) > 0:
            return f"{hours}h ago"
        return f"{(delta.seconds % 3600) // 60}m ago"

    @staticmethod
    def truncate_text(
        text: Optional[str], max_length: int = 20, placeholder: str = "..."
    ) -> str:
        """Truncate text to specified length and add placeholder if needed."""
        if not text:
            return ""
        text = text.strip()
        if len(text) <= max_length:
            return text
        return f"{text[:max_length - len(placeholder)]}{placeholder}"


class TablePrinter:
    """Table formatting and printing utilities."""

    def __init__(self):
        """Initialize printer."""
        self.formatter = TextFormatter()

    def print_table(
        self, headers: List[str], rows: List[Tuple[Any, ...]], widths: List[int]
    ) -> None:
        """Print formatted table with headers and rows."""
        total_width = sum(widths) + len(widths) - 1
        separator = "-" * total_width
        row_format = " ".join(f"{{:<{w}}}" for w in widths)

        print(separator)
        print(row_format.format(*headers))
        print(separator)

        for row in rows:
            formatted_row = [
                str(val)[:width] if isinstance(val, str) else str(val)
                for val, width in zip(row, widths)
            ]
            print(row_format.format(*formatted_row))

        print(separator)
        print(f"Total: {len(rows)}")


class ProfileChecker:
    """Profile information checker and displayer."""

    def __init__(self):
        """Initialize checker."""
        self.printer = TablePrinter()
        self.formatter = TextFormatter()

    def format_template_row(self, template) -> Tuple:
        """Format single template row."""
        return (
            template.id,
            self.formatter.truncate_text(template.name, 20),
            self.formatter.truncate_text(template.first_name, 15),
            self.formatter.truncate_text(template.last_name or "", 15),
            self.formatter.truncate_text(template.bio, 20),
            "Yes" if template.is_active else "No",
            (
                f"Account #{template.source_account_id}"
                if template.source_account_id
                else "Manual"
            ),
        )

    def format_profile_row(self, profile) -> Tuple:
        """Format single profile row."""
        return (
            profile.account_id,
            self.formatter.truncate_text(
                profile.template.name if profile.template else "No template", 20
            ),
            self.formatter.truncate_text(profile.first_name, 15),
            self.formatter.truncate_text(profile.last_name or "", 15),
            self.formatter.truncate_text(profile.bio, 20),
            "Yes" if profile.is_synced else "No",
            self.formatter.format_datetime(profile.last_synced_at),
            self.formatter.format_datetime(profile.last_telegram_update),
            f"{len(profile.history)} changes ({profile.history[0].change_type if profile.history else 'No changes'})",
        )

    def format_account_row(self, account) -> Tuple:
        """Format single account row."""
        return (
            account.id,
            self.formatter.truncate_text(account.phone, 15),
            self.formatter.truncate_text(account.status.value, 15),
            account.daily_messages,
            self.formatter.format_datetime(account.last_used_at),
        )

    def display_templates(self, templates) -> None:
        """Display profile templates."""
        print("\nProfile templates:")
        self.printer.print_table(
            headers=[
                "ID",
                "Name",
                "First Name",
                "Last Name",
                "Bio",
                "Active",
                "Source",
            ],
            rows=[self.format_template_row(t) for t in templates],
            widths=[5, 20, 15, 15, 20, 8, 20],
        )

    def display_profiles(self, profiles) -> None:
        """Display account profiles."""
        print("\nAccount profiles:")
        self.printer.print_table(
            headers=[
                "Account ID",
                "Template",
                "First Name",
                "Last Name",
                "Bio",
                "Synced",
                "Last Sync",
                "TG Update",
                "History",
            ],
            rows=[self.format_profile_row(p) for p in profiles],
            widths=[10, 20, 15, 15, 20, 8, 10, 10, 30],
        )

    def display_accounts_without_profiles(self, accounts) -> None:
        """Display accounts without profiles."""
        print("\nAccounts without profiles:")
        self.printer.print_table(
            headers=["ID", "Phone", "Status", "Messages", "Last Used"],
            rows=[self.format_account_row(a) for a in accounts],
            widths=[5, 15, 15, 10, 20],
        )

    @with_queries((AccountQueries, ProfileQueries))
    async def check_profiles(
        self, account_queries: AccountQueries, profile_queries: ProfileQueries
    ) -> None:
        """Check and display information about all profiles in database."""
        # Get templates
        templates = await profile_queries.get_active_templates()
        self.display_templates(templates)

        # Get profiles with relationships
        profiles = await profile_queries.get_all_profiles(
            options=[
                selectinload(AccountProfile.history),
                selectinload(AccountProfile.template),
            ]
        )
        self.display_profiles(profiles)

        # Get accounts without profiles
        profile_account_ids = {p.account_id for p in profiles}
        accounts = await account_queries.get_all_accounts()
        accounts_without_profiles = [
            a for a in accounts if a.id not in profile_account_ids
        ]
        self.display_accounts_without_profiles(accounts_without_profiles)


def main():
    """Main entry point."""
    checker = ProfileChecker()
    asyncio.run(checker.check_profiles())
