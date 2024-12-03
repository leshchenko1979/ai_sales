"""Account queries."""

import logging
from typing import List, Optional

from core.db.base import BaseQueries
from sqlalchemy import and_, select

from ..models.account import Account, AccountStatus

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

    async def _create_account(
        self, phone: str, status: AccountStatus
    ) -> Optional[Account]:
        """Internal method to create an account."""
        try:
            account = Account(phone=phone, status=status)
            self.session.add(account)
            await self.session.commit()
            return account
        except Exception as e:
            logger.error(f"Failed to create account for {phone}: {e}")
            await self.session.rollback()
            return None

    async def create_account(self, phone: str) -> Optional[Account]:
        """Create new account."""
        return await self._create_account(phone, AccountStatus.new)

    async def get_or_create_account(self, phone: str) -> Optional[Account]:
        """Get or create account by phone number."""
        account = await self.get_account_by_phone(phone)
        return account or await self._create_account(phone, AccountStatus.active)

    async def get_available_account(self) -> Optional[Account]:
        """Get available account for messaging."""
        try:
            query = (
                select(Account)
                .where(
                    and_(
                        Account.status == AccountStatus.active,
                        Account.session_string.is_not(None),
                        (Account.daily_messages < 40)
                        | (Account.daily_messages.is_(None)),
                    )
                )
                .order_by(Account.last_used_at.asc().nullsfirst())
            )
            result = await self.session.execute(query)
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error(f"Failed to get available account: {e}", exc_info=True)
            return None

    async def get_accounts_by_status(self, status: AccountStatus) -> List[Account]:
        """Get accounts by status."""
        try:
            query = (
                select(Account)
                .where(Account.status == status)
                .order_by(Account.last_used_at.asc().nullsfirst())
            )
            result = await self.session.execute(query)
            return list(result.scalars().all())
        except Exception as e:
            logger.error(f"Failed to get {status} accounts: {e}")
            return []

    async def get_all_accounts(self) -> List[Account]:
        """Get all accounts."""
        return await self.get_accounts_by_status(None)

    async def get_active_accounts(self) -> List[Account]:
        """Get all active accounts."""
        return await self.get_accounts_by_status(AccountStatus.active)

    async def get_any_active_account(self) -> Optional[Account]:
        """Get any active account with session."""
        try:
            query = (
                select(Account)
                .where(
                    and_(
                        Account.status == AccountStatus.active,
                        Account.session_string.is_not(None),
                    )
                )
                .order_by(Account.last_used_at.asc().nullsfirst())
                .limit(1)
            )
            result = await self.session.execute(query)
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error(f"Failed to get any active account: {e}")
            return None

    async def get_available_accounts(self) -> List[Account]:
        """Get all available accounts."""
        try:
            query = (
                select(Account)
                .where(
                    and_(
                        Account.status == AccountStatus.active,
                        Account.session_string.is_not(None),
                    )
                )
                .order_by(Account.last_used_at.asc())
            )
            result = await self.session.execute(query)
            return list(result.scalars().all())
        except Exception as e:
            logger.error(f"Failed to get available accounts: {e}")
            return []
