import asyncio
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).parent.parent
sys.path.append(str(ROOT_DIR))

import click
from core.campaigns.models import CampaignStatus
from core.campaigns.queries import CampaignQueries
from core.db import with_queries


@click.group()
def cli():
    """Campaign management commands."""


@cli.command()
@click.option("--name", required=True, help="Campaign name")
@click.option("--company-id", required=True, type=int, help="Company ID")
@click.option("--engine-type", required=True, help="Dialog engine type")
@click.option("--prompt", required=True, help="Prompt template")
@click.option("--active", is_flag=True, help="Set campaign as active")
@with_queries(CampaignQueries)
async def create(
    queries: CampaignQueries,
    name: str,
    company_id: int,
    engine_type: str,
    prompt: str,
    active: bool,
):
    """Create new campaign."""
    status = CampaignStatus.ACTIVE if active else CampaignStatus.INACTIVE

    campaign = await queries.create_campaign(
        name=name,
        company_id=company_id,
        dialog_engine_type=engine_type,
        prompt_template=prompt,
        status=status,
    )

    click.echo(f"Created campaign {campaign.id}: {campaign.name}")


@cli.command()
@click.option("--campaign-id", required=True, type=int, help="Campaign ID")
@click.option("--account-id", required=True, type=int, help="Account ID")
@with_queries(CampaignQueries)
async def add_account(queries: CampaignQueries, campaign_id: int, account_id: int):
    """Add account to campaign."""
    campaign = await queries.add_account_to_campaign(campaign_id, account_id)
    if campaign:
        click.echo(f"Added account {account_id} to campaign {campaign_id}")
    else:
        click.echo("Campaign or account not found")


@cli.command()
@click.option("--campaign-id", required=True, type=int, help="Campaign ID")
@click.option("--template-id", required=True, type=int, help="Template ID")
@with_queries(CampaignQueries)
async def add_template(queries: CampaignQueries, campaign_id: int, template_id: int):
    """Add profile template to campaign."""
    campaign = await queries.add_profile_template_to_campaign(campaign_id, template_id)
    if campaign:
        click.echo(f"Added template {template_id} to campaign {campaign_id}")
    else:
        click.echo("Campaign or template not found")


@cli.command()
@click.option("--campaign-id", required=True, type=int, help="Campaign ID")
@click.option("--active/--inactive", required=True, help="New status")
@with_queries(CampaignQueries)
async def set_status(queries: CampaignQueries, campaign_id: int, active: bool):
    """Set campaign status."""
    status = CampaignStatus.ACTIVE if active else CampaignStatus.INACTIVE
    campaign = await queries.update_campaign_status(campaign_id, status)
    if campaign:
        click.echo(f"Updated campaign {campaign_id} status to {status.value}")
    else:
        click.echo("Campaign not found")


if __name__ == "__main__":
    asyncio.run(cli())
