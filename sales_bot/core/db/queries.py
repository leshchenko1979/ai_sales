"""Database queries."""

import logging
from datetime import datetime
from typing import List, Optional

from core.accounts.models import Account, AccountStatus
from core.messages.models import Dialog, Message
from sqlalchemy import select, update

from .base import BaseQueries

logger = logging.getLogger(__name__)


class AccountQueries(BaseQueries):
    """Queries for working with accounts."""

    async def get_account_by_phone(self, phone: str) -> Optional[Account]:
        """Get account by phone number."""
        try:
            result = await self.session.execute(
                select(Account).where(Account.phone == phone)
            )
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error(f"Error getting account by phone {phone}: {e}", exc_info=True)
            return None

    async def get_account_by_id(self, account_id: int) -> Optional[Account]:
        """Get account by ID."""
        try:
            return await self.session.get(Account, account_id)
        except Exception as e:
            logger.error(
                f"Error getting account by ID {account_id}: {e}", exc_info=True
            )
            return None

    async def get_active_accounts(self) -> List[Account]:
        """Get all active accounts ordered by message count."""
        result = await self.session.execute(
            select(Account)
            .where(Account.status == AccountStatus.active)
            .order_by(Account.daily_messages)
        )
        return list(result.scalars().all())

    async def get_all_accounts(self) -> List[Account]:
        """Get all accounts regardless of their status."""
        query = select(Account)
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def create_account(self, phone_number: str) -> Account:
        """Create new account."""
        # Check if account exists
        existing_account = await self.session.execute(
            select(Account).filter_by(phone=phone_number)
        )
        existing_account = existing_account.scalar_one_or_none()
        if existing_account:
            return existing_account

        # Create new account
        new_account = Account(
            phone=phone_number,
            status=AccountStatus.new,
            session_string=None,
            last_warmup_at=None,
            flood_wait_until=None,
            messages_sent=0,
            is_available=True,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )

        self.session.add(new_account)
        await self.session.commit()
        await self.session.refresh(new_account)
        return new_account

    async def update_session_string(self, account_id: int, session_string: str) -> bool:
        """Update account session string."""
        try:
            result = await self.session.execute(
                update(Account)
                .where(Account.id == account_id)
                .values(session_string=session_string)
            )
            await self.session.commit()
            return result.rowcount > 0
        except Exception as e:
            await self.session.rollback()
            logger.error(f"Error updating session string: {e}", exc_info=True)
            raise

    async def update_account_status(
        self, account_id: int, status: AccountStatus
    ) -> bool:
        """Update account status."""
        try:
            account = await self.session.get(Account, account_id)
            if not account:
                return False

            account.status = status
            account.updated_at = datetime.utcnow()
            self.session.add(account)
            return True

        except Exception as e:
            logger.error(f"Error updating account status: {e}", exc_info=True)
            return False

    async def reset_daily_limits(self) -> bool:
        """Reset daily message limits for all accounts."""
        try:
            result = await self.session.execute(
                update(Account).values(daily_messages=0)
            )
            await self.session.commit()
            return result.rowcount > 0
        except Exception as e:
            await self.session.rollback()
            logger.error(f"Error resetting daily limits: {e}", exc_info=True)
            raise

    async def increment_messages(self, account_id: int) -> bool:
        """Increment daily message counter."""
        try:
            account = await self.session.get(Account, account_id)
            if not account:
                return False

            account.daily_messages += 1
            account.messages_sent += 1
            account.last_used_at = datetime.utcnow()
            self.session.add(account)
            return True

        except Exception as e:
            logger.error(f"Error incrementing messages: {e}", exc_info=True)
            return False


class DialogQueries(BaseQueries):
    """Queries for working with dialogs."""

    async def create_dialog(self, username: str, account_id: int) -> Optional[Dialog]:
        """Create new dialog."""
        try:
            dialog = Dialog(
                username=username,
                account_id=account_id,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )
            self.session.add(dialog)
            await self.session.commit()
            await self.session.refresh(dialog)
            return dialog

        except Exception as e:
            await self.session.rollback()
            logger.error(f"Error creating dialog: {e}", exc_info=True)
            return None

    async def get_dialog(self, username: str, account_id: int) -> Optional[Dialog]:
        """Get dialog by username and account ID."""
        try:
            result = await self.session.execute(
                select(Dialog).where(
                    Dialog.username == username,
                    Dialog.account_id == account_id,
                )
            )
            return result.scalar_one_or_none()

        except Exception as e:
            logger.error(f"Error getting dialog: {e}", exc_info=True)
            return None

    async def save_message(
        self, dialog_id: int, content: str, direction: str
    ) -> Optional[Message]:
        """Save message to dialog."""
        try:
            message = Message(
                dialog_id=dialog_id,
                content=content,
                direction=direction,
                timestamp=datetime.utcnow(),
            )
            self.session.add(message)
            await self.session.commit()
            await self.session.refresh(message)
            return message

        except Exception as e:
            await self.session.rollback()
            logger.error(f"Error saving message: {e}", exc_info=True)
            raise

    async def get_all_dialogs(self) -> list[Dialog]:
        """Get all dialogs from the database."""
        query = select(Dialog).order_by(Dialog.created_at.desc())
        result = await self.session.execute(query)
        return list(result.scalars().all())
