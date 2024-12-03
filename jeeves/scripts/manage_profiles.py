#!/usr/bin/env python3
"""Profile management tool."""

import asyncio
import logging
import sys
from pathlib import Path
from typing import Optional

ROOT_DIR = Path(__file__).parent.parent
sys.path.append(str(ROOT_DIR))

from core.accounts.models import AccountStatus
from core.accounts.models.profile import ProfileTemplate
from core.accounts.queries.account import AccountQueries
from core.accounts.queries.profile import ProfileQueries
from core.db.decorators import with_queries

logger = logging.getLogger(__name__)


class AccountDisplay:
    """Account display helper."""

    def __init__(self):
        """Initialize display."""
        self.separator = "-" * 120

    def print_header(self):
        """Print table header."""
        print("\nAvailable accounts:")
        print(self.separator)
        print(
            f"{'ID':<5} {'Phone':<15} {'Name':<20} {'Status':<10} {'Has Session':<12} "
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

        profile_name = (
            f"{account.profile.first_name} {account.profile.last_name or ''}"
            if account.profile
            else "-"
        ).strip()

        print(
            f"{account.id:<5} "
            f"{account.phone:<15} "
            f"{profile_name[:20]:<20} "
            f"{account.status.value:<10} "
            f"{'Yes' if account.session_string else 'No':<12} "
            f"{account.daily_messages or 0:<10} "
            f"{'Yes' if can_be_used else 'No'}"
        )


@with_queries(ProfileQueries)
async def list_templates(queries: ProfileQueries) -> list[ProfileTemplate]:
    """List all profile templates."""
    templates = await queries.get_active_templates()

    if not templates:
        print("No active templates found")
        return []

    print("\nActive templates:")
    for template in templates:
        print(f"\n[{template.id}] {template.name}:")
        print(f"  First name: {template.first_name}")
        print(f"  Last name: {template.last_name or '-'}")
        print(f"  Bio: {template.bio or '-'}")

    return templates


@with_queries(ProfileQueries)
async def create_template(
    name: str,
    first_name: str,
    queries: ProfileQueries,
    last_name: Optional[str] = None,
    bio: Optional[str] = None,
    photo_path: Optional[str] = None,
) -> None:
    """Create new profile template."""
    photo_data = None
    if photo_path:
        try:
            with open(photo_path, "rb") as f:
                photo_data = f.read()
        except Exception as e:
            logger.error(f"Failed to read photo file {photo_path}: {e}")
            return

    template = await queries.create_template(
        name=name,
        first_name=first_name,
        last_name=last_name,
        bio=bio,
        photo=photo_data,
    )

    if template:
        print(f"\nCreated template '{template.name}'")
    else:
        print("\nFailed to create template")

    return template


@with_queries((ProfileQueries, AccountQueries))
async def apply_template(
    profile_queries: ProfileQueries,
    account_queries: AccountQueries,
    account_id: int,
    template_id: int,
) -> None:
    """Apply template to account profile."""
    # Verify account exists
    account = await account_queries.get_account_by_id(account_id)
    if not account:
        print(f"\nAccount {account_id} not found")
        return

    profile = await profile_queries.apply_template(account_id, template_id)

    if profile:
        print(f"\nApplied template to account {account_id}")
    else:
        print(f"\nFailed to apply template to account {account_id}")


@with_queries(ProfileQueries)
async def delete_template(queries: ProfileQueries, template_id: int) -> None:
    """Delete profile template."""
    success = await queries.delete_template(template_id)

    if success:
        print(f"\nDeleted template {template_id}")
    else:
        print(f"\nFailed to delete template {template_id}")


@with_queries(ProfileQueries)
async def update_template(
    queries: ProfileQueries,
    template_id: int,
    name: Optional[str] = None,
    first_name: Optional[str] = None,
    last_name: Optional[str] = None,
    bio: Optional[str] = None,
    photo_path: Optional[str] = None,
) -> None:
    """Update profile template."""
    photo_data = None
    if photo_path:
        try:
            with open(photo_path, "rb") as f:
                photo_data = f.read()
        except Exception as e:
            logger.error(f"Failed to read photo file {photo_path}: {e}")
            return

    updates = {
        "name": name,
        "first_name": first_name,
        "last_name": last_name,
        "bio": bio,
        "photo": photo_data,
    }
    # Remove None values
    updates = {k: v for k, v in updates.items() if v is not None}

    success = await queries.update_template(template_id, **updates)

    if success:
        print(f"\nUpdated template {template_id}")
    else:
        print(f"\nFailed to update template {template_id}")


async def interactive_create_template() -> None:
    """Interactive template creation."""
    print("\nCreating new template")
    print("-" * 20)

    name = input("Template name: ").strip()
    while not name:
        print("Name cannot be empty")
        name = input("Template name: ").strip()

    first_name = input("First name: ").strip()
    while not first_name:
        print("First name cannot be empty")
        first_name = input("First name: ").strip()

    last_name = input("Last name (optional): ").strip() or None
    bio = input("Bio (optional): ").strip() or None

    await create_template(
        name=name, first_name=first_name, last_name=last_name, bio=bio
    )


@with_queries((ProfileQueries, AccountQueries))
async def interactive_apply_template(
    profile_queries: ProfileQueries,
    account_queries: AccountQueries,
) -> None:
    """Interactive template application."""
    # First show templates
    templates = await list_templates()
    if not templates:
        return

    # Get and display active accounts
    accounts = await account_queries.get_active_accounts()
    if not accounts:
        print("\nNo active accounts found")
        return

    # Display accounts table
    display = AccountDisplay()
    display.print_header()
    for account in accounts:
        display.print_account_info(account)
    print(display.separator)

    print("\nApplying template")
    print("-" * 20)

    # Get template ID
    while True:
        try:
            template_id = int(input("\nEnter template ID: "))
            if any(t.id == template_id for t in templates):
                break
            print("Invalid template ID")
        except ValueError:
            print("Please enter a number")

    # Get account ID
    while True:
        try:
            account_id = int(input("Enter account ID: "))
            if any(a.id == account_id for a in accounts):
                account = next(a for a in accounts if a.id == account_id)
                if not account.session_string:
                    print("Selected account has no session")
                    continue
                if account.status != AccountStatus.active:
                    print("Selected account is not active")
                    continue
                break
            print("Invalid account ID")
        except ValueError:
            print("Please enter a number")

    # Apply template
    await apply_template(account_id=account_id, template_id=template_id)


async def interactive_update_template() -> None:
    """Interactive template update."""
    templates = await list_templates()
    if not templates:
        return

    print("\nUpdating template")
    print("-" * 20)

    while True:
        try:
            template_id = int(input("\nEnter template ID: "))
            if any(t.id == template_id for t in templates):
                break
            print("Invalid template ID")
        except ValueError:
            print("Please enter a number")

    print("\nEnter new values (press Enter to keep current value):")
    name = input("Template name: ").strip() or None
    first_name = input("First name: ").strip() or None
    last_name = input("Last name: ").strip() or None
    bio = input("Bio: ").strip() or None
    photo_path = input("Photo path (optional): ").strip() or None

    await update_template(
        template_id=template_id,
        name=name,
        first_name=first_name,
        last_name=last_name,
        bio=bio,
        photo_path=photo_path,
    )


async def interactive_delete_template() -> None:
    """Interactive template deletion."""
    templates = await list_templates()
    if not templates:
        return

    print("\nDeleting template")
    print("-" * 20)

    while True:
        try:
            template_id = int(input("\nEnter template ID: "))
            if any(t.id == template_id for t in templates):
                break
            print("Invalid template ID")
        except ValueError:
            print("Please enter a number")

    confirm = input(
        f"\nAre you sure you want to delete template {template_id}? (y/N): "
    )
    if confirm.lower() == "y":
        await delete_template(template_id)
    else:
        print("Deletion cancelled")


async def interactive_menu() -> None:
    """Interactive menu."""
    while True:
        print("\nProfile Management")
        print("-" * 20)
        print("1. List templates")
        print("2. Create template")
        print("3. Update template")
        print("4. Delete template")
        print("5. Apply template")
        print("6. Exit")

        choice = input("\nEnter choice (1-6): ").strip()

        if choice == "1":
            await list_templates()
        elif choice == "2":
            await interactive_create_template()
        elif choice == "3":
            await interactive_update_template()
        elif choice == "4":
            await interactive_delete_template()
        elif choice == "5":
            await interactive_apply_template()
        elif choice == "6":
            break
        else:
            print("Invalid choice")


async def main():
    """Run profile management tool."""
    import argparse

    parser = argparse.ArgumentParser(description="Profile management tool")
    parser.add_argument(
        "-i", "--interactive", action="store_true", help="Run in interactive mode"
    )

    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # List templates
    subparsers.add_parser("list", help="List all active templates")

    # Create template
    create_parser = subparsers.add_parser("create", help="Create new template")
    create_parser.add_argument("name", help="Template name")
    create_parser.add_argument("first_name", help="Profile first name")
    create_parser.add_argument("--last-name", help="Profile last name")
    create_parser.add_argument("--bio", help="Profile bio")
    create_parser.add_argument("--photo", help="Path to profile photo")

    # Update template
    update_parser = subparsers.add_parser("update", help="Update template")
    update_parser.add_argument("template_id", type=int, help="Template ID")
    update_parser.add_argument("--name", help="New template name")
    update_parser.add_argument("--first-name", help="New first name")
    update_parser.add_argument("--last-name", help="New last name")
    update_parser.add_argument("--bio", help="New bio")
    update_parser.add_argument("--photo", help="New profile photo path")

    # Delete template
    delete_parser = subparsers.add_parser("delete", help="Delete template")
    delete_parser.add_argument("template_id", type=int, help="Template ID")

    # Apply template
    apply_parser = subparsers.add_parser("apply", help="Apply template to account")
    apply_parser.add_argument("account_id", type=int, help="Account ID")
    apply_parser.add_argument("template_id", type=int, help="Template ID")

    args = parser.parse_args()

    if args.interactive:
        await interactive_menu()
        return

    if args.command == "list":
        await list_templates()

    elif args.command == "create":
        await create_template(
            name=args.name,
            first_name=args.first_name,
            last_name=args.last_name,
            bio=args.bio,
            photo_path=args.photo,
        )

    elif args.command == "update":
        await update_template(
            template_id=args.template_id,
            name=args.name,
            first_name=args.first_name,
            last_name=args.last_name,
            bio=args.bio,
            photo_path=args.photo,
        )

    elif args.command == "delete":
        await delete_template(args.template_id)

    elif args.command == "apply":
        await apply_template(args.account_id, args.template_id)

    else:
        parser.print_help()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, EOFError):
        print("\nExiting...")
