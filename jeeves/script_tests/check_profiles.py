"""Script to check account profiles in database."""

import asyncio
import sys
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

# Add project root to path
root_dir = Path(__file__).parent.parent
sys.path.append(str(root_dir))

load_dotenv()

from core.accounts.queries.account import AccountQueries
from core.accounts.queries.profile import ProfileQueries
from core.db import with_queries


def format_datetime(dt: datetime | None) -> str:
    """Format datetime for display."""
    if not dt:
        return "Never"

    # Convert naive datetime to aware if needed
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)

    now = datetime.now(timezone.utc)
    delta = now - dt
    if delta.days > 0:
        return f"{delta.days}d ago"
    hours = delta.seconds // 3600
    if hours > 0:
        return f"{hours}h ago"
    minutes = (delta.seconds % 3600) // 60
    return f"{minutes}m ago"


@with_queries((AccountQueries, ProfileQueries))
async def check_profiles(
    account_queries: AccountQueries, profile_queries: ProfileQueries
):
    """Check all profiles in database."""
    # Get all templates
    print("\nProfile templates:")
    print("-" * 120)
    print(
        f"{'ID':<5} {'Name':<20} {'First Name':<15} {'Last Name':<15} "
        f"{'Bio':<20} {'Active':<8} {'Source'}"
    )
    print("-" * 120)

    templates = await profile_queries.get_active_templates()
    for template in templates:
        source = (
            f"Account #{template.source_account_id}"
            if template.source_account_id
            else "Manual"
        )
        bio = (
            template.bio[:20] + "..."
            if template.bio and len(template.bio) > 20
            else template.bio or ""
        )
        print(
            f"{template.id:<5} "
            f"{template.name[:20]:<20} "
            f"{template.first_name[:15]:<15} "
            f"{(template.last_name or '')[:15]:<15} "
            f"{bio:<20} "
            f"{'Yes' if template.is_active else 'No':<8} "
            f"{source}"
        )
    print("-" * 120)
    print(f"Total templates: {len(templates)}")

    # Get all profiles
    print("\nAccount profiles:")
    print("-" * 120)
    print(
        f"{'Account ID':<10} {'Template':<20} {'First Name':<15} {'Last Name':<15} "
        f"{'Bio':<20} {'Synced':<8} {'Last Sync':<10} {'TG Update':<10} {'History'}"
    )
    print("-" * 120)

    profiles = await profile_queries.get_all_profiles()
    profile_account_ids = {p.account_id for p in profiles}

    for profile in profiles:
        template_name = profile.template.name if profile.template else "No template"
        bio = (
            profile.bio[:20] + "..."
            if profile.bio and len(profile.bio) > 20
            else profile.bio or ""
        )
        history_count = len(profile.history)
        last_change = (
            profile.history[0].change_type if history_count > 0 else "No changes"
        )

        # Format sync info
        last_sync = format_datetime(profile.last_synced_at)
        last_tg = format_datetime(profile.last_telegram_update)

        print(
            f"{profile.account_id:<10} "
            f"{template_name[:20]:<20} "
            f"{profile.first_name[:15]:<15} "
            f"{(profile.last_name or '')[:15]:<15} "
            f"{bio:<20} "
            f"{'Yes' if profile.is_synced else 'No':<8} "
            f"{last_sync:<10} "
            f"{last_tg:<10} "
            f"{history_count} changes ({last_change})"
        )
    print("-" * 120)
    print(f"Total profiles: {len(profiles)}")

    # Check accounts without profiles
    print("\nAccounts without profiles:")
    print("-" * 80)
    print(f"{'ID':<5} {'Phone':<15} {'Status':<15} {'Messages':<10} {'Last Used'}")
    print("-" * 80)

    accounts = await account_queries.get_all_accounts()
    accounts_without_profiles = [a for a in accounts if a.id not in profile_account_ids]

    for account in accounts_without_profiles:
        last_used = format_datetime(account.last_used_at)
        print(
            f"{account.id:<5} "
            f"{account.phone:<15} "
            f"{account.status.value:<15} "
            f"{account.daily_messages:<10} "
            f"{last_used}"
        )
    print("-" * 80)
    print(f"Total accounts without profiles: {len(accounts_without_profiles)}")


if __name__ == "__main__":
    asyncio.run(check_profiles())
