import csv
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).parent.parent
sys.path.append(str(ROOT_DIR))

import click
from core.audiences.models import AudienceStatus
from core.audiences.queries import AudienceQueries
from core.db import with_queries


@click.group()
def cli():
    """Audience management commands."""


@cli.command()
@click.option("--name", required=True, help="Audience name")
@click.option("--company-id", required=True, type=int, help="Company ID")
@click.option("--description", help="Audience description")
@with_queries(AudienceQueries)
async def create(
    queries: AudienceQueries, name: str, company_id: int, description: str = None
):
    """Create new audience."""
    audience = await queries.create_audience(
        name=name, company_id=company_id, description=description
    )
    click.echo(f"Created audience {audience.id}: {audience.name}")


@cli.command()
@click.option("--company-id", required=True, type=int, help="Company ID")
@with_queries(AudienceQueries)
async def list(queries: AudienceQueries, company_id: int):
    """List all company audiences."""
    audiences = await queries.get_company_audiences(company_id)

    if not audiences:
        click.echo("No audiences found")
        return

    for audience in audiences:
        stats = await queries.get_audience_stats(audience.id)
        click.echo(
            f"ID: {audience.id}, Name: {audience.name}, "
            f"Status: {audience.status.value}, "
            f"Contacts: {stats['valid_contacts']}/{stats['total_contacts']}"
        )


@cli.command()
@click.option("--audience-id", required=True, type=int, help="Audience ID")
@click.option(
    "--file", required=True, type=click.Path(exists=True), help="CSV file with contacts"
)
@click.option("--has-header", is_flag=True, help="CSV file has header row")
@with_queries(AudienceQueries)
async def import_contacts(
    queries: AudienceQueries, audience_id: int, file: str, has_header: bool
):
    """Import contacts from CSV file."""
    # Check audience exists
    audience = await queries.get_audience(audience_id)
    if not audience:
        click.echo("Audience not found")
        return

    contact_ids = []
    new_contacts = 0
    existing_contacts = 0

    with open(file, "r") as f:
        reader = csv.reader(f)
        if has_header:
            next(reader)

        for row in reader:
            if len(row) < 1:
                continue

            # Try to parse username and phone
            username = row[0].strip() if row[0].strip() else None
            phone = row[1].strip() if len(row) > 1 and row[1].strip() else None

            if not username and not phone:
                continue

            # Check if contact exists
            contact = await queries.find_contact(username=username, phone=phone)

            if contact:
                existing_contacts += 1
            else:
                contact = await queries.create_contact(username=username, phone=phone)
                new_contacts += 1

            contact_ids.append(contact.id)

    # Add contacts to audience
    if contact_ids:
        await queries.add_contacts_to_audience(audience_id, contact_ids)
        await queries.update_audience_status(audience_id, AudienceStatus.ready)

    click.echo(
        f"Imported {new_contacts} new contacts, "
        f"found {existing_contacts} existing contacts"
    )


@cli.command()
@click.option("--audience-id", required=True, type=int, help="Audience ID")
@click.option("--valid-only", is_flag=True, help="Show only valid contacts")
@with_queries(AudienceQueries)
async def show_contacts(queries: AudienceQueries, audience_id: int, valid_only: bool):
    """Show audience contacts."""
    contacts = await queries.get_audience_contacts(audience_id, valid_only=valid_only)

    if not contacts:
        click.echo("No contacts found")
        return

    for contact in contacts:
        click.echo(
            f"ID: {contact.id}, "
            f"Username: {contact.username or 'N/A'}, "
            f"Phone: {contact.phone or 'N/A'}, "
            f"Valid: {contact.is_valid}"
        )


if __name__ == "__main__":
    cli()
