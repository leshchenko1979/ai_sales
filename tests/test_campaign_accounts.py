"""Tests for campaign-account operations."""

import pytest
from core.accounts.models import Account, AccountStatus
from core.accounts.queries import AccountQueries
from core.campaigns.models import Campaign
from core.campaigns.queries import CampaignQueries
from core.companies.models import Company
from sqlalchemy.ext.asyncio import AsyncSession


@pytest.mark.asyncio
async def test_remove_account_from_campaign(session: AsyncSession):
    """Test that removing an account from campaign doesn't delete it from DB."""
    # Create test company
    company = Company(name="Test Company", is_active=True)
    session.add(company)
    await session.flush()

    # Create test account
    account = Account(id=123456789, phone="+79189999999", status=AccountStatus.active)
    session.add(account)

    # Create test campaign
    campaign = Campaign(
        name="Test Campaign",
        is_active=True,
        company_id=company.id,
        dialog_strategy="cold_meetings",
    )
    session.add(campaign)
    await session.flush()

    # Add account to campaign
    campaign_queries = CampaignQueries(session)
    await campaign_queries.add_account_to_campaign(campaign.id, account.id)

    # Verify account is in campaign
    campaign = await campaign_queries.get_campaign(campaign.id)
    assert len(campaign.accounts) == 1
    assert campaign.accounts[0].id == account.id

    # Remove account from campaign
    await campaign_queries.remove_account_from_campaign(campaign.id, account.id)

    # Verify account is removed from campaign
    campaign = await campaign_queries.get_campaign(campaign.id)
    assert len(campaign.accounts) == 0

    # Verify account still exists in database
    account_queries = AccountQueries(session)
    existing_account = await account_queries.get_account_by_id(account.id)
    assert existing_account is not None
    assert existing_account.id == account.id


@pytest.mark.asyncio
async def test_add_account_to_campaign_twice(session: AsyncSession):
    """Test that we can't add the same account to campaign twice."""
    # Create test company
    company = Company(name="Test Company", is_active=True)
    session.add(company)
    await session.flush()

    # Create test account
    account = Account(id=123456789, phone="+79189999999", status=AccountStatus.active)
    session.add(account)

    # Create test campaign
    campaign = Campaign(
        name="Test Campaign",
        is_active=True,
        company_id=company.id,
        dialog_strategy="cold_meetings",
    )
    session.add(campaign)
    await session.flush()

    # Add account to campaign twice
    campaign_queries = CampaignQueries(session)
    await campaign_queries.add_account_to_campaign(campaign.id, account.id)
    await campaign_queries.add_account_to_campaign(campaign.id, account.id)

    # Verify account is only in campaign once
    campaign = await campaign_queries.get_campaign(campaign.id)
    assert len(campaign.accounts) == 1
    assert campaign.accounts[0].id == account.id


@pytest.mark.asyncio
async def test_remove_nonexistent_account_from_campaign(session: AsyncSession):
    """Test removing an account that's not in the campaign."""
    # Create test company
    company = Company(name="Test Company", is_active=True)
    session.add(company)
    await session.flush()

    # Create test campaign
    campaign = Campaign(
        name="Test Campaign",
        is_active=True,
        company_id=company.id,
        dialog_strategy="cold_meetings",
    )
    session.add(campaign)
    await session.flush()

    # Create test account (but don't add to campaign)
    account = Account(id=123456789, phone="+79189999999", status=AccountStatus.active)
    session.add(account)
    await session.flush()

    # Try to remove account that was never added
    campaign_queries = CampaignQueries(session)
    await campaign_queries.remove_account_from_campaign(campaign.id, account.id)

    # Verify campaign is unchanged
    campaign = await campaign_queries.get_campaign(campaign.id)
    assert len(campaign.accounts) == 0
