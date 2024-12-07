from typing import List, Optional

from core.db.queries import BaseQueries
from sqlalchemy import select

from .models import Campaign, CampaignStatus


class CampaignQueries(BaseQueries):
    """Queries for campaigns."""

    async def create_campaign(
        self,
        name: str,
        company_id: int,
        dialog_engine_type: str,
        prompt_template: str,
        status: CampaignStatus = CampaignStatus.INACTIVE,
    ) -> Campaign:
        """Create new campaign."""
        campaign = Campaign(
            name=name,
            company_id=company_id,
            dialog_engine_type=dialog_engine_type,
            prompt_template=prompt_template,
            status=status,
        )
        self.session.add(campaign)
        await self.session.flush()
        return campaign

    async def get_campaign(self, campaign_id: int) -> Optional[Campaign]:
        """Get campaign by ID."""
        query = select(Campaign).where(Campaign.id == campaign_id)
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def get_active_campaigns(self) -> List[Campaign]:
        """Get all active campaigns."""
        query = select(Campaign).where(Campaign.status == CampaignStatus.ACTIVE)
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def update_campaign_status(
        self, campaign_id: int, status: CampaignStatus
    ) -> Optional[Campaign]:
        """Update campaign status."""
        campaign = await self.get_campaign(campaign_id)
        if campaign:
            campaign.status = status
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

        account_queries = AccountQueries(self.session)
        account = await account_queries.get_account(account_id)
        if not account:
            return None

        campaign.accounts.append(account)
        await self.session.flush()
        return campaign

    async def add_profile_template_to_campaign(
        self, campaign_id: int, template_id: int
    ) -> Optional[Campaign]:
        """Add profile template to campaign."""
        from core.profiles.queries import ProfileTemplateQueries

        campaign = await self.get_campaign(campaign_id)
        if not campaign:
            return None

        template_queries = ProfileTemplateQueries(self.session)
        template = await template_queries.get_template(template_id)
        if not template:
            return None

        campaign.profile_templates.append(template)
        await self.session.flush()
        return campaign
