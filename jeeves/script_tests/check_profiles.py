"""Script to check account profiles in database."""

import asyncio
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from sqlalchemy.orm import selectinload

# Add project root to path
root_dir = Path(__file__).parent.parent
sys.path.append(str(root_dir))

load_dotenv()

from core.accounts.models.profile import AccountProfile
from core.accounts.queries.account import AccountQueries
from core.accounts.queries.profile import ProfileQueries
from core.db import with_queries


def format_datetime(dt: datetime | None) -> str:
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


def truncate_text(
    text: str | None, max_length: int = 20, placeholder: str = "..."
) -> str:
    """Truncate text to specified length and add placeholder if needed.

    Args:
        text: Text to truncate
        max_length: Maximum length of the resulting text
        placeholder: String to append when text is truncated
    """
    if not text:
        return ""
    text = text.strip()
    if len(text) <= max_length:
        return text
    return f"{text[:max_length - len(placeholder)]}{placeholder}"


def print_table(
    headers: list[str], rows: list[tuple[Any, ...]], widths: list[int]
) -> None:
    """Print formatted table with headers and rows."""
    total_width = sum(widths) + len(widths) - 1  # Account for spaces between columns
    separator = "-" * total_width
    row_format = " ".join(f"{{:<{w}}}" for w in widths)

    print(separator)
    print(row_format.format(*headers))
    print(separator)

    for row in rows:
        # Convert all values to strings and ensure proper length
        formatted_row = [
            str(val)[:width] if isinstance(val, str) else str(val)
            for val, width in zip(row, widths)
        ]
        print(row_format.format(*formatted_row))

    print(separator)
    print(f"Total: {len(rows)}")


@with_queries((AccountQueries, ProfileQueries))
async def check_profiles(
    account_queries: AccountQueries, profile_queries: ProfileQueries
) -> None:
    """Check and display information about all profiles in database."""
    # Get templates data
    templates = await profile_queries.get_active_templates()
    template_rows = [
        (
            template.id,
            truncate_text(template.name, 20),
            truncate_text(template.first_name, 15),
            truncate_text(template.last_name or "", 15),
            truncate_text(template.bio, 20),
            "Yes" if template.is_active else "No",
            (
                f"Account #{template.source_account_id}"
                if template.source_account_id
                else "Manual"
            ),
        )
        for template in templates
    ]

    print("\nProfile templates:")
    print_table(
        headers=["ID", "Name", "First Name", "Last Name", "Bio", "Active", "Source"],
        rows=template_rows,
        widths=[5, 20, 15, 15, 20, 8, 20],
    )

    # Get profiles with preloaded relationships
    profiles = await profile_queries.get_all_profiles(
        options=[
            selectinload(AccountProfile.history),
            selectinload(AccountProfile.template),
        ]
    )

    profile_rows = [
        (
            profile.account_id,
            truncate_text(
                profile.template.name if profile.template else "No template", 20
            ),
            truncate_text(profile.first_name, 15),
            truncate_text(profile.last_name or "", 15),
            truncate_text(profile.bio, 20),
            "Yes" if profile.is_synced else "No",
            format_datetime(profile.last_synced_at),
            format_datetime(profile.last_telegram_update),
            f"{len(profile.history)} changes ({profile.history[0].change_type if profile.history else 'No changes'})",
        )
        for profile in profiles
    ]

    print("\nAccount profiles:")
    print_table(
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
        rows=profile_rows,
        widths=[10, 20, 15, 15, 20, 8, 10, 10, 30],
    )

    # Get accounts without profiles
    profile_account_ids = {p.account_id for p in profiles}
    accounts = await account_queries.get_all_accounts()
    accounts_without_profiles = [a for a in accounts if a.id not in profile_account_ids]

    account_rows = [
        (
            account.id,
            truncate_text(account.phone, 15),
            truncate_text(account.status.value, 15),
            account.daily_messages,
            format_datetime(account.last_used_at),
        )
        for account in accounts_without_profiles
    ]

    print("\nAccounts without profiles:")
    print_table(
        headers=["ID", "Phone", "Status", "Messages", "Last Used"],
        rows=account_rows,
        widths=[5, 15, 15, 10, 20],
    )


if __name__ == "__main__":
    asyncio.run(check_profiles())
