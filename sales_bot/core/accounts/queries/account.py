"""Account queries."""

import logging
from typing import Optional

from core.accounts.models import Account, AccountStatus
from core.db.base import BaseQueries
from sqlalchemy import select

logger = logging.getLogger(__name__)


class AccountQueries(BaseQueries):
    """Queries for working with accounts."""

    async def update_account(self, phone: str, **updates) -> Optional[Account]:
        """Update account with given values."""
        try:
            account = await self.get_account_by_phone(phone)
            if not account:
                return None

            for key, value in updates.items():
                setattr(account, key, value)
            self.session.add(account)
            await self.session.commit()
            return account
        except Exception as e:
            logger.error(f"Failed to update account {phone}: {e}")
            await self.session.rollback()
            return None

    async def get_account_by_phone(self, phone: str) -> Optional[Account]:
        """Get account by phone number."""
        try:
            query = select(Account).where(Account.phone == phone)
            result = await self.session.execute(query)
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error(f"Failed to get account by phone {phone}: {e}")
            return None

    async def get_all_accounts(self) -> list[Account]:
        """Get all accounts."""
        try:
            query = select(Account).order_by(Account.id)
            result = await self.session.execute(query)
            return list(result.scalars().all())
        except Exception as e:
            logger.error(f"Failed to get all accounts: {e}")
            return []

    async def create_account(self, phone: str) -> Optional[Account]:
        """Create new account."""
        try:
            account = Account(
                phone=phone,
                status=AccountStatus.new,
            )
            self.session.add(account)
            await self.session.commit()
            return account
        except Exception as e:
            logger.error(f"Failed to create account for {phone}: {e}")
            await self.session.rollback()
            return None

    async def get_or_create_account(self, phone: str) -> Optional[Account]:
        """Get or create account by phone number."""
        try:
            account = await self.get_account_by_phone(phone)
            if account:
                return account

            account = Account(
                phone=phone,
                status=AccountStatus.active,
            )
            self.session.add(account)
            await self.session.commit()
            return account
        except Exception as e:
            logger.error(f"Failed to get or create account for {phone}: {e}")
            await self.session.rollback()
            return None

    async def get_available_account(self) -> Optional[Account]:
        """Get available account."""
        try:
            query = (
                select(Account)
                .where(Account.status == AccountStatus.active)
                .order_by(Account.last_used_at.asc())
            )
            result = await self.session.execute(query)
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error(f"Failed to get available account: {e}")
            return None
