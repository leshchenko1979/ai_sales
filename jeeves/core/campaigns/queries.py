from typing import List, Optional

from core.audiences.models import Audience
from core.db.base import BaseQueries
from core.db.tables import campaigns_accounts
from sqlalchemy import delete, select
from sqlalchemy.orm import selectinload

from .models import Campaign


class CampaignQueries(BaseQueries):
    """Queries for campaigns."""

    async def create_campaign(
        self,
        name: str,
        company_id: int,
        dialog_strategy: str,
        is_active: bool = False,
    ) -> Campaign:
        """Create new campaign."""
        campaign = Campaign(
            name=name,
            company_id=company_id,
            dialog_strategy=dialog_strategy,
            is_active=is_active,
        )
        self.session.add(campaign)
        await self.session.flush()
        return campaign

    async def get_campaign(self, campaign_id: int) -> Optional[Campaign]:
        """Get campaign by ID."""
        query = (
            select(Campaign)
            .where(Campaign.id == campaign_id)
            .options(
                selectinload(Campaign.accounts),
                selectinload(Campaign.profile_templates),
                selectinload(Campaign.company),
                selectinload(Campaign.audiences),
            )
        )
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def get_active_campaigns(self) -> List[Campaign]:
        """Get all active campaigns."""
        query = (
            select(Campaign)
            .where(Campaign.is_active == True)  # noqa: E712
            .options(
                selectinload(Campaign.accounts),
                selectinload(Campaign.profile_templates),
                selectinload(Campaign.company),
                selectinload(Campaign.audiences),
            )
        )
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def get_all_campaigns(self) -> List[Campaign]:
        """Get all campaigns regardless of status."""
        query = (
            select(Campaign)
            .order_by(Campaign.id)
            .options(
                selectinload(Campaign.accounts),
                selectinload(Campaign.profile_templates),
                selectinload(Campaign.company),
                selectinload(Campaign.audiences),
            )
        )
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def update_campaign_status(
        self, campaign_id: int, is_active: bool
    ) -> Optional[Campaign]:
        """Update campaign status."""
        campaign = await self.get_campaign(campaign_id)
        if campaign:
            campaign.is_active = is_active
            await self.session.flush()
        return campaign

    async def add_account_to_campaign(
        self, campaign_id: int, account_id: int
    ) -> Optional[Campaign]:
        """Add account to campaign."""
        from core.accounts.queries import AccountQueries

        campaign = await self.get_campaign(campaign_id)
        if not campaign:
            return None

        # Check if account is already in campaign
        if any(a.id == account_id for a in campaign.accounts):
            return campaign  # Account already in campaign

        account_queries = AccountQueries(self.session)
        account = await account_queries.get_account_by_id(account_id)
        if not account:
            return None

        # Add account to campaign's accounts list
        campaign.accounts.append(account)
        await self.session.flush()
        return campaign

    async def remove_account_from_campaign(
        self, campaign_id: int, account_id: int
    ) -> Optional[Campaign]:
        """Remove account from campaign."""
        campaign = await self.get_campaign(campaign_id)
        if not campaign:
            return None

        # Remove the association using SQL DELETE
        # This is safer than manipulating the list directly
        stmt = delete(campaigns_accounts).where(
            campaigns_accounts.c.campaign_id == campaign_id,
            campaigns_accounts.c.account_id == account_id,
        )
        await self.session.execute(stmt)
        await self.session.flush()

        # Refresh the campaign to get updated accounts list
        await self.session.refresh(campaign)
        return campaign

    async def add_profile_template_to_campaign(
        self, campaign_id: int, template_id: int
    ) -> Optional[Campaign]:
        """Add profile template to campaign."""
        from core.accounts.queries.profile import ProfileQueries

        campaign = await self.get_campaign(campaign_id)
        if not campaign:
            return None

        template_queries = ProfileQueries(self.session)
        template = await template_queries.get_template(template_id)
        if not template:
            return None

        campaign.profile_templates.append(template)
        await self.session.flush()
        return campaign

    async def add_audience_to_campaign(
        self, campaign_id: int, audience_id: int
    ) -> Optional[Campaign]:
        """Add audience to campaign."""
        campaign = await self.get_campaign(campaign_id)
        if not campaign:
            return None

        # Check if audience is already in campaign
        if any(a.id == audience_id for a in campaign.audiences):
            return campaign  # Audience already in campaign

        # Get the audience
        audience = await self.session.get(Audience, audience_id)
        if not audience:
            return None

        campaign.audiences.append(audience)
        await self.session.flush()
        return campaign

    async def remove_audience_from_campaign(
        self, campaign_id: int, audience_id: int
    ) -> Optional[Campaign]:
        """Remove audience from campaign."""
        campaign = await self.get_campaign(campaign_id)
        if not campaign:
            return None

        # Remove the audience using list comprehension
        campaign.audiences = [a for a in campaign.audiences if a.id != audience_id]
        await self.session.flush()
        return campaign
