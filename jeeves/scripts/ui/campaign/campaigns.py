"""Campaign-specific UI operations."""

import asyncio

import questionary
from core import db
from core.accounts import queries as account_queries
from core.audiences.queries import AudienceQueries
from core.campaigns import queries as campaign_queries
from core.campaigns.models import Campaign

from ..styles import STYLE


class CampaignUI:
    """Campaign UI operations."""

    def __init__(self, manager):
        """Initialize with parent manager."""
        self.manager = manager

    @db.with_queries(campaign_queries.CampaignQueries)
    async def view_campaigns(self, queries: campaign_queries.CampaignQueries):
        """View and manage existing campaigns."""
        while True:
            try:
                campaigns = await queries.get_all_campaigns()
                if not campaigns:
                    print("No campaigns found")
                    await self.manager._pause()
                    return

                print("\nAvailable Campaigns:")
                self.manager.print_separator()
                for campaign in campaigns:
                    status = "active" if campaign.is_active else "inactive"
                    "green" if campaign.is_active else "red"
                    print(f"ID: {campaign.id}")
                    print(f"Name: {campaign.name}")
                    print(f"Status: {status}")
                    print(
                        f"Company: {campaign.company.name if campaign.company else 'N/A'}"
                    )
                    print(f"Accounts: {len(campaign.accounts)}")
                    print(f"Templates: {len(campaign.profile_templates)}")
                    print(f"Audiences: {len(campaign.audiences)}")
                    self.manager.print_separator()

                # Create choices for questionary
                choices = [
                    questionary.Choice(
                        f"{campaign.name} (ID: {campaign.id}, {status})", campaign.id
                    )
                    for campaign in campaigns
                ]
                choices.append(questionary.Choice("Back", "back"))

                choice = await questionary.select(
                    "Select campaign to manage:", choices=choices, style=STYLE
                ).ask_async()

                if choice == "back":
                    break

                campaign = await queries.get_campaign(choice)
                if campaign:
                    await self.manage_campaign_details(campaign)
                else:
                    print("Campaign not found")
                    await self.manager._pause()

            except (KeyboardInterrupt, asyncio.CancelledError):
                break
            except Exception as e:
                self.manager._handle_error(e)
                await self.manager._pause()

    @db.with_queries((campaign_queries.CampaignQueries, account_queries.AccountQueries))
    async def campaign_quick_actions(
        self,
        campaign_queries: campaign_queries.CampaignQueries,
        account_queries: account_queries.AccountQueries,
    ):
        """Quick actions for campaign management."""
        while True:
            try:
                print("\nCampaign Quick Actions")
                self.manager.print_separator()

                choice = await questionary.select(
                    "Select action:",
                    choices=[
                        questionary.Choice("Change Campaign Status", 1),
                        questionary.Choice("Add Account to Campaign", 2),
                        questionary.Choice("Add Template to Campaign", 3),
                        questionary.Choice("Back", 0),
                    ],
                    style=STYLE,
                ).ask_async()

                if choice == 0:
                    break
                elif choice == 1:
                    await self.change_campaign_status()
                elif choice == 2:
                    await self.add_account_to_campaign()
                elif choice == 3:
                    await self.add_template_to_campaign()

            except (KeyboardInterrupt, asyncio.CancelledError):
                break
            except Exception as e:
                self.manager._handle_error(e)
                await self.manager._pause()

    @db.with_queries(
        (
            campaign_queries.CampaignQueries,
            account_queries.AccountQueries,
            AudienceQueries,
        )
    )
    async def manage_campaign_details(
        self,
        campaign: Campaign,
        campaign_queries: campaign_queries.CampaignQueries,
        account_queries: account_queries.AccountQueries,
        audience_queries: AudienceQueries,
    ):
        """Manage details of a specific campaign."""
        while True:
            try:
                print(f"\nCampaign: {campaign.name}")
                self.manager.print_separator()

                choice = await questionary.select(
                    "Select action:",
                    choices=[
                        questionary.Choice("Overview", 1),
                        questionary.Choice("Audience Management", 2),
                        questionary.Choice("Account Management", 3),
                        questionary.Choice("Template Management", 4),
                        questionary.Choice("Campaign Settings", 5),
                        questionary.Choice("Back", 0),
                    ],
                    style=STYLE,
                ).ask_async()

                if choice == 0:
                    break
                elif choice == 1:
                    await self._show_campaign_details(campaign)
                elif choice == 2:
                    await self._handle_manage_audiences(campaign)
                elif choice == 3:
                    await self._handle_account_management(campaign)
                elif choice == 4:
                    await self._handle_template_management(campaign)
                elif choice == 5:
                    await self._handle_campaign_settings(campaign)

                # Refresh campaign data after operations
                updated_campaign = await campaign_queries.get_campaign(campaign.id)
                if updated_campaign:
                    campaign = updated_campaign
                else:
                    print("Campaign no longer exists!")
                    await self.manager._pause()
                    return

            except (KeyboardInterrupt, asyncio.CancelledError):
                break
            except Exception as e:
                self.manager._handle_error(e)
                await self.manager._pause()

    async def _show_campaign_details(self, campaign: Campaign):
        """Show detailed information about a campaign."""
        print(f"\nCampaign Details: {campaign.name}")
        self.manager.print_separator()

        # Basic info
        print(f"ID: {campaign.id}")
        print(f"Status: {'active' if campaign.is_active else 'inactive'}")

        # Company info
        if campaign.company:
            print(f"\nCompany: {campaign.company.name}")
            print(
                f"Company Status: {'active' if campaign.company.is_active else 'inactive'}"
            )
        else:
            print("\nNo company assigned")

        # Accounts info
        print(f"\nAccounts ({len(campaign.accounts)}):")
        for account in campaign.accounts:
            print(f"- {account.phone} ({account.status})")

        # Templates info
        print(f"\nProfile Templates ({len(campaign.profile_templates)}):")
        for template in campaign.profile_templates:
            print(f"- {template.name}")

        # Audiences info
        print(f"\nAudiences ({len(campaign.audiences)}):")
        for audience in campaign.audiences:
            print(f"- {audience.name} ({len(audience.contacts)} contacts)")

        await self.manager._pause()

    @db.with_queries((campaign_queries.CampaignQueries, account_queries.AccountQueries))
    async def _handle_account_management(
        self,
        campaign: Campaign,
        campaign_queries: campaign_queries.CampaignQueries,
        account_queries: account_queries.AccountQueries,
    ):
        """Handle account management for campaign."""
        while True:
            try:
                print("\nAccount Management")
                self.manager.print_separator()

                choice = await questionary.select(
                    "Select action:",
                    choices=[
                        questionary.Choice("View Accounts", 1),
                        questionary.Choice("Add Account", 2),
                        questionary.Choice("Remove Account", 3),
                        questionary.Choice("Back", 0),
                    ],
                    style=STYLE,
                ).ask_async()

                if choice == 0:
                    break
                elif choice == 1:
                    await self._view_campaign_accounts(campaign)
                elif choice == 2:
                    await self._add_account_to_campaign(campaign)
                elif choice == 3:
                    await self._remove_account_from_campaign(campaign)

            except (KeyboardInterrupt, asyncio.CancelledError):
                break
            except Exception as e:
                self.manager._handle_error(e)
                await self.manager._pause()

    async def _view_campaign_accounts(self, campaign: Campaign):
        """View accounts in campaign."""
        print(f"\nAccounts in campaign {campaign.name}:")
        self.manager.print_separator()

        if not campaign.accounts:
            print("No accounts in this campaign")
        else:
            for account in campaign.accounts:
                print(f"Phone: {account.phone}")
                print(f"Status: {account.status}")
                print(f"Session: {'Yes' if account.session_string else 'No'}")
                self.manager.print_separator()

        await self.manager._pause()

    @db.with_queries((campaign_queries.CampaignQueries, account_queries.AccountQueries))
    async def _add_account_to_campaign(
        self,
        campaign: Campaign,
        campaign_queries: campaign_queries.CampaignQueries,
        account_queries: account_queries.AccountQueries,
    ):
        """Add account to campaign."""
        # Get available accounts
        all_accounts = await account_queries.get_all_accounts()
        campaign_account_ids = {account.id for account in campaign.accounts}
        available_accounts = [
            account
            for account in all_accounts
            if account.id not in campaign_account_ids
        ]

        if not available_accounts:
            print("\nNo available accounts to add")
            await self.manager._pause()
            return

        # Create choices for questionary
        choices = [
            questionary.Choice(f"{account.phone} ({account.status})", account.id)
            for account in available_accounts
        ]
        choices.append(questionary.Choice("Back", "back"))

        # Let user select account
        choice = await questionary.select(
            "Select account to add:", choices=choices, style=STYLE
        ).ask_async()

        if choice == "back":
            return

        # Add account to campaign
        try:
            await campaign_queries.add_account_to_campaign(campaign.id, choice)
            print("\nAccount added successfully")
        except Exception as e:
            print(f"\nError adding account: {e}")

        await self.manager._pause()

    @db.with_queries(campaign_queries.CampaignQueries)
    async def _remove_account_from_campaign(
        self,
        campaign: Campaign,
        queries: campaign_queries.CampaignQueries,
    ):
        """Remove account from campaign."""
        if not campaign.accounts:
            print("\nNo accounts in this campaign")
            await self.manager._pause()
            return

        # Create choices for questionary
        choices = [
            questionary.Choice(f"{account.phone} ({account.status})", account.id)
            for account in campaign.accounts
        ]
        choices.append(questionary.Choice("Back", "back"))

        # Let user select account
        choice = await questionary.select(
            "Select account to remove:", choices=choices, style=STYLE
        ).ask_async()

        if choice == "back":
            return

        # Remove account from campaign
        try:
            await queries.remove_account_from_campaign(campaign.id, choice)
            print("\nAccount removed successfully")
        except Exception as e:
            print(f"\nError removing account: {e}")

        await self.manager._pause()

    @db.with_queries((campaign_queries.CampaignQueries, AudienceQueries))
    async def _handle_manage_audiences(
        self,
        campaign: Campaign,
        campaign_queries: campaign_queries.CampaignQueries,
        audience_queries: AudienceQueries,
    ):
        """Handle audience management for campaign."""
        while True:
            try:
                print("\nAudience Management")
                self.manager.print_separator()

                choice = await questionary.select(
                    "Select action:",
                    choices=[
                        questionary.Choice("View Audiences", 1),
                        questionary.Choice("Add Audience", 2),
                        questionary.Choice("Remove Audience", 3),
                        questionary.Choice("Back", 0),
                    ],
                    style=STYLE,
                ).ask_async()

                if choice == 0:
                    break
                elif choice == 1:
                    await self._view_campaign_audiences(campaign)
                elif choice == 2:
                    await self._add_audience_to_campaign(
                        campaign, campaign_queries, audience_queries
                    )
                elif choice == 3:
                    await self._remove_audience_from_campaign(
                        campaign, campaign_queries
                    )

            except (KeyboardInterrupt, asyncio.CancelledError):
                break
            except Exception as e:
                self.manager._handle_error(e)
                await self.manager._pause()

    async def _view_campaign_audiences(self, campaign: Campaign):
        """View audiences in campaign."""
        print(f"\nAudiences in campaign {campaign.name}:")
        self.manager.print_separator()

        if not campaign.audiences:
            print("No audiences in this campaign")
        else:
            for audience in campaign.audiences:
                print(f"Name: {audience.name}")
                print(f"Contacts: {len(audience.contacts)}")
                print(f"Status: {'active' if audience.is_active else 'inactive'}")
                self.manager.print_separator()

        await self.manager._pause()

    @db.with_queries((campaign_queries.CampaignQueries, AudienceQueries))
    async def _add_audience_to_campaign(
        self,
        campaign: Campaign,
        campaign_queries: campaign_queries.CampaignQueries,
        audience_queries: AudienceQueries,
    ):
        """Add audience to campaign."""
        # Get available audiences
        all_audiences = await audience_queries.get_all_audiences()
        available_audiences = [
            audience for audience in all_audiences if audience not in campaign.audiences
        ]

        if not available_audiences:
            print("\nNo available audiences to add")
            await self.manager._pause()
            return

        # Create choices for questionary
        choices = [
            questionary.Choice(
                f"{audience.name} ({len(audience.contacts)} contacts)", audience.id
            )
            for audience in available_audiences
        ]
        choices.append(questionary.Choice("Back", "back"))

        # Let user select audience
        choice = await questionary.select(
            "Select audience to add:", choices=choices, style=STYLE
        ).ask_async()

        if choice == "back":
            return

        # Add audience to campaign
        try:
            await campaign_queries.add_audience_to_campaign(campaign.id, choice)
            print("\nAudience added successfully")
        except Exception as e:
            print(f"\nError adding audience: {e}")

        await self.manager._pause()

    @db.with_queries(campaign_queries.CampaignQueries)
    async def _remove_audience_from_campaign(
        self,
        campaign: Campaign,
        campaign_queries: campaign_queries.CampaignQueries,
    ):
        """Remove audience from campaign."""
        if not campaign.audiences:
            print("\nNo audiences in this campaign")
            await self.manager._pause()
            return

        # Create choices for questionary
        choices = [
            questionary.Choice(
                f"{audience.name} ({len(audience.contacts)} contacts)", audience.id
            )
            for audience in campaign.audiences
        ]
        choices.append(questionary.Choice("Back", "back"))

        # Let user select audience
        choice = await questionary.select(
            "Select audience to remove:", choices=choices, style=STYLE
        ).ask_async()

        if choice == "back":
            return

        # Remove audience from campaign
        try:
            await campaign_queries.remove_audience_from_campaign(campaign.id, choice)
            print("\nAudience removed successfully")
        except Exception as e:
            print(f"\nError removing audience: {e}")

        await self.manager._pause()

    # ... Add other campaign-specific methods here ...
