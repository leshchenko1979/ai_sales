"""Audience management UI operations."""

import asyncio

import questionary
from core import db
from core.audiences import queries as audience_queries
from core.campaigns import queries as campaign_queries
from core.campaigns.models import Campaign

from ..styles import STYLE


class AudienceUI:
    """Audience UI operations."""

    def __init__(self, manager):
        """Initialize with parent manager."""
        self.manager = manager

    @db.with_queries(
        (campaign_queries.CampaignQueries, audience_queries.AudienceQueries)
    )
    async def _handle_manage_audiences(
        self,
        campaign: Campaign,
        campaign_queries: campaign_queries.CampaignQueries,
        audience_queries: audience_queries.AudienceQueries,
    ):
        """Handle audience management for campaign."""
        while True:
            try:
                print("\nAudience Management")
                self.manager.print_separator()

                # Show current audiences
                print("\nCurrent audiences:")
                self.manager.print_separator()
                if not campaign.audiences:
                    print("No audiences assigned")
                else:
                    for audience in campaign.audiences:
                        print(f"ID: {audience.id}")
                        print(f"Name: {audience.name}")
                        if audience.description:
                            print(f"Description: {audience.description}")
                        if audience.status:
                            print(f"Status: {audience.status.value}")
                        self.manager.print_separator()

                choice = await questionary.select(
                    "Select action:",
                    choices=[
                        questionary.Choice("Add Audience", 1),
                        questionary.Choice("Remove Audience", 2),
                        questionary.Choice("Back", 0),
                    ],
                    style=STYLE,
                ).ask_async()

                if choice == 0:
                    break
                elif choice == 1:
                    await self._handle_add_audience(campaign)
                elif choice == 2:
                    if not campaign.audiences:
                        print("No audiences to remove")
                        await self.manager._pause()
                        continue

                    # Create choices for audience removal
                    choices = [
                        questionary.Choice(
                            f"{audience.name} (ID: {audience.id}, Status: {audience.status.value})",
                            audience.id,
                        )
                        for audience in campaign.audiences
                    ]
                    choices.append(questionary.Choice("Cancel", "cancel"))

                    audience_id = await questionary.select(
                        "Select audience to remove:", choices=choices, style=STYLE
                    ).ask_async()

                    if audience_id != "cancel":
                        updated_campaign = (
                            await campaign_queries.remove_audience_from_campaign(
                                campaign.id, audience_id
                            )
                        )
                        if updated_campaign:
                            print(f"Removed audience {audience_id}")
                        else:
                            print("Failed to remove audience")
                        await self.manager._pause()

            except (KeyboardInterrupt, asyncio.CancelledError):
                break
            except Exception as e:
                self.manager._handle_error(e)
                await self.manager._pause()

    @db.with_queries(
        (campaign_queries.CampaignQueries, audience_queries.AudienceQueries)
    )
    async def _handle_add_audience(
        self,
        campaign: Campaign,
        campaign_queries: campaign_queries.CampaignQueries,
        audience_queries: audience_queries.AudienceQueries,
    ):
        """Handle adding audience to campaign."""
        # Get list of audience IDs already in campaign
        campaign_audience_ids = {a.id for a in campaign.audiences}

        # Get available audiences
        audiences = await audience_queries.get_available_audiences()
        if not audiences:
            print("No audiences available")
            await self.manager._pause()
            return

        print("\nAvailable audiences:")
        self.manager.print_separator()

        # Create choices for audience selection
        choices = []
        for audience in audiences:
            # Skip if already in campaign
            if audience.id in campaign_audience_ids:
                continue

            print(f"ID: {audience.id}")
            print(f"Name: {audience.name}")
            if audience.description:
                print(f"Description: {audience.description}")
            print(f"Status: {audience.status.value}")
            self.manager.print_separator()

            choices.append(
                questionary.Choice(
                    f"{audience.name} (ID: {audience.id}, Status: {audience.status.value})",
                    audience.id,
                )
            )

        if not choices:
            print("No available audiences to add")
            await self.manager._pause()
            return

        choices.append(questionary.Choice("Cancel", "cancel"))

        audience_id = await questionary.select(
            "Select audience to add:", choices=choices, style=STYLE
        ).ask_async()

        if audience_id != "cancel":
            updated_campaign = await campaign_queries.add_audience_to_campaign(
                campaign.id, audience_id
            )
            if updated_campaign:
                print(f"Added audience {audience_id}")
            else:
                print("Failed to add audience")
            await self.manager._pause()
