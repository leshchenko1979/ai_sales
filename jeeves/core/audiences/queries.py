from typing import List, Optional

from core.audiences.models import Audience, AudienceStatus, Contact
from core.campaigns.models import Campaign
from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload


class AudienceQueries:
    """Queries for working with audiences and contacts."""

    def __init__(self, session: Session):
        self.session = session

    # Audience queries
    async def create_audience(
        self,
        name: str,
        description: Optional[str] = None,
        status: AudienceStatus = AudienceStatus.new,
    ) -> Audience:
        """Create new audience."""
        audience = Audience(
            name=name,
            description=description,
            status=status,
        )
        self.session.add(audience)
        await self.session.flush()
        return audience

    async def get_audience(self, audience_id: int) -> Optional[Audience]:
        """Get audience by ID."""
        query = select(Audience).where(Audience.id == audience_id)
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def get_campaign_audiences(self, campaign_id: int) -> List[Audience]:
        """Get all audiences for a campaign."""
        query = (
            select(Campaign)
            .options(joinedload(Campaign.audiences))
            .where(Campaign.id == campaign_id)
        )
        result = await self.session.execute(query)
        campaign = result.unique().scalar_one_or_none()
        return campaign.audiences if campaign else []

    async def get_available_audiences(self) -> List[Audience]:
        """Get all available audiences."""
        query = select(Audience).where(Audience.status == AudienceStatus.ready)
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def update_audience_status(
        self, audience_id: int, status: AudienceStatus
    ) -> Optional[Audience]:
        """Update audience status."""
        audience = await self.get_audience(audience_id)
        if audience:
            audience.status = status
            await self.session.flush()
        return audience

    # Contact queries
    async def create_contact(
        self, username: Optional[str] = None, phone: Optional[str] = None
    ) -> Contact:
        """Create new contact."""
        if not username and not phone:
            raise ValueError("Either username or phone must be provided")

        contact = Contact(username=username, phone=phone)
        self.session.add(contact)
        await self.session.flush()
        return contact

    async def get_contact(self, contact_id: int) -> Optional[Contact]:
        """Get contact by ID."""
        query = select(Contact).where(Contact.id == contact_id)
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def find_contact(
        self, username: Optional[str] = None, phone: Optional[str] = None
    ) -> Optional[Contact]:
        """Find contact by username or phone."""
        if not username and not phone:
            raise ValueError("Either username or phone must be provided")

        query = select(Contact)
        if username:
            query = query.where(Contact.username == username)
        if phone:
            query = query.where(Contact.phone == phone)

        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    # Audience-Contact relationship queries
    async def add_contacts_to_audience(
        self, audience_id: int, contact_ids: List[int]
    ) -> Optional[Audience]:
        """Add contacts to audience."""
        audience = await self.get_audience(audience_id)
        if not audience:
            return None

        contacts = await self.session.execute(
            select(Contact).where(Contact.id.in_(contact_ids))
        )
        contacts = contacts.scalars().all()

        audience.contacts.extend(contacts)
        audience.total_contacts = len(audience.contacts)
        await self.session.flush()
        return audience

    async def get_audience_contacts(
        self, audience_id: int, valid_only: bool = False
    ) -> List[Contact]:
        """Get all contacts in audience."""
        query = (
            select(Contact).join(Contact.audiences).where(Audience.id == audience_id)
        )

        if valid_only:
            query = query.where(Contact.is_valid == True)  # noqa: E712

        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def get_audience_stats(self, audience_id: int) -> dict:
        """Get audience statistics."""
        total = (
            select(func.count())
            .select_from(Contact)
            .join(Contact.audiences)
            .where(Audience.id == audience_id)
            .scalar_subquery()
        )

        valid = (
            select(func.count())
            .select_from(Contact)
            .join(Contact.audiences)
            .where(Audience.id == audience_id)
            .where(Contact.is_valid == True)  # noqa: E712
            .scalar_subquery()
        )

        result = await self.session.execute(
            select(total.label("total"), valid.label("valid"))
        )
        stats = result.one()

        return {"total_contacts": stats.total, "valid_contacts": stats.valid}
