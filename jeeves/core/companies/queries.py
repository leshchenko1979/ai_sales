from typing import List, Optional

from core.db.base import BaseQueries
from sqlalchemy import select

from .models import Company


class CompanyQueries(BaseQueries):
    """Queries for companies."""

    async def create_company(
        self, name: str, descriptions: dict | None = None, is_active: bool = True
    ) -> Company:
        """Create new company."""
        company = Company(name=name, descriptions=descriptions, is_active=is_active)
        self.session.add(company)
        await self.session.flush()
        return company

    async def get_company(self, company_id: int) -> Optional[Company]:
        """Get company by ID."""
        query = select(Company).where(Company.id == company_id)
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def get_active_companies(self) -> List[Company]:
        """Get all active companies."""
        query = select(Company).where(Company.is_active.is_(True))
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def get_all_companies(self) -> List[Company]:
        """Get all companies regardless of status."""
        query = select(Company).order_by(Company.id)
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def update_company_status(self, company_id: int, is_active: bool) -> Company:
        """Update company status."""
        company = await self.session.get(Company, company_id)
        if company:
            company.is_active = is_active
            await self.session.flush()
        return company

    async def update_company(
        self,
        company_id: int,
        name: str,
        descriptions: dict | None = None,
    ) -> Company:
        """Update company details."""
        company = await self.session.get(Company, company_id)
        if company:
            company.name = name
            company.descriptions = descriptions
            await self.session.flush()
        return company
