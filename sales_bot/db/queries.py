import logging
import os
from contextlib import asynccontextmanager
from datetime import datetime
from typing import List, Optional

from config import DATABASE_URL
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from .models import Account, AccountStatus, Dialog, Message

logger = logging.getLogger(__name__)

# Update the DATABASE_URL to use asyncpg
DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://")

# Create async engine
engine = create_async_engine(DATABASE_URL) if not os.getenv("TESTING") else None

# Create async session factory
AsyncSessionLocal = (
    sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    if not os.getenv("TESTING")
    else None
)


@asynccontextmanager
async def get_db():
    """Get database session"""
    if AsyncSessionLocal is None:
        raise RuntimeError("Database is not initialized")

    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception as e:
            await session.rollback()
            logger.error(f"Database error: {e}", exc_info=True)
            raise


class AccountQueries:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_account_by_phone(self, phone: str) -> Optional[Account]:
        """Get account by phone number"""
        result = await self.session.execute(
            select(Account).where(Account.phone == phone)
        )
        return result.scalar_one_or_none()

    async def get_account_by_id(self, account_id: int) -> Optional[Account]:
        """Get account by ID"""
        result = await self.session.execute(
            select(Account).where(Account.id == account_id)
        )
        return result.scalar_one_or_none()

    async def get_active_accounts(self) -> List[Account]:
        """Get all active accounts ordered by message count"""
        result = await self.session.execute(
            select(Account)
            .where(Account.status == AccountStatus.ACTIVE)
            .order_by(Account.daily_messages)
        )
        return result.scalars().all()

    async def get_accounts_by_status(self, status: AccountStatus) -> List[Account]:
        """Get accounts by status"""
        result = await self.session.execute(
            select(Account)
            .where(Account.status == status)
            .order_by(Account.last_used.nulls_first())
        )
        return result.scalars().all()

    async def get_accounts_for_warmup(self) -> List[Account]:
        """Get accounts for warmup"""
        result = await self.session.execute(
            select(Account).where(Account.status == AccountStatus.ACTIVE)
        )
        return result.scalars().all()

    async def update_account_status(self, phone: str, status: AccountStatus) -> bool:
        """Update account status"""
        try:
            result = await self.session.execute(
                update(Account).where(Account.phone == phone).values(status=status)
            )
            await self.session.commit()
            return result.rowcount > 0
        except Exception as e:
            await self.session.rollback()
            logger.error(f"Error updating account status: {e}", exc_info=True)
            raise

    async def update_account_status_by_id(
        self, account_id: int, status: AccountStatus
    ) -> bool:
        """Update account status by ID"""
        try:
            result = await self.session.execute(
                update(Account).where(Account.id == account_id).values(status=status)
            )
            await self.session.commit()
            return result.rowcount > 0
        except Exception as e:
            await self.session.rollback()
            logger.error(f"Error updating account status: {e}", exc_info=True)
            raise

    async def create_account(self, phone: str) -> Optional[Account]:
        """Create new account"""
        try:
            account = Account(
                phone=phone, status=AccountStatus.ACTIVE, daily_messages=0
            )
            self.session.add(account)
            await self.session.commit()
            await self.session.refresh(account)
            return account
        except Exception as e:
            await self.session.rollback()
            logger.error(f"Error creating account: {e}", exc_info=True)
            raise

    async def update_session(self, account_id: int, session_string: str) -> bool:
        """Update account session string"""
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
            logger.error(f"Error updating session: {e}", exc_info=True)
            raise

    async def increment_messages(self, account_id: int) -> bool:
        """Increment daily message counter"""
        try:
            result = await self.session.execute(
                update(Account)
                .where(Account.id == account_id)
                .values(
                    daily_messages=Account.daily_messages + 1, last_used=datetime.now()
                )
            )
            await self.session.commit()
            return result.rowcount > 0
        except Exception as e:
            await self.session.rollback()
            logger.error(f"Error incrementing messages: {e}", exc_info=True)
            raise

    async def update_account_warmup_time(self, account_id: int) -> bool:
        """Update account warmup timestamp"""
        try:
            result = await self.session.execute(
                update(Account)
                .where(Account.id == account_id)
                .values(last_warmup=datetime.now())
            )
            await self.session.commit()
            return result.rowcount > 0
        except Exception as e:
            await self.session.rollback()
            logger.error(f"Error updating warmup time: {e}", exc_info=True)
            raise


class DialogQueries:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_dialog(self, username: str, account_id: int) -> Optional[Dialog]:
        """Create new dialog"""
        try:
            dialog = Dialog(
                target_username=username, account_id=account_id, status="active"
            )
            self.session.add(dialog)
            await self.session.commit()
            await self.session.refresh(dialog)
            return dialog
        except Exception as e:
            await self.session.rollback()
            logger.error(f"Error creating dialog: {e}", exc_info=True)
            raise

    async def get_dialog(self, dialog_id: int) -> Optional[Dialog]:
        """Get dialog by ID"""
        result = await self.session.execute(
            select(Dialog).where(Dialog.id == dialog_id)
        )
        return result.scalar_one_or_none()

    async def get_active_dialogs(self) -> List[Dialog]:
        """Get all active dialogs"""
        result = await self.session.execute(
            select(Dialog).where(Dialog.status == "active")
        )
        return result.scalars().all()

    async def get_messages(self, dialog_id: int) -> List[Message]:
        """Get all messages for a dialog"""
        result = await self.session.execute(
            select(Message)
            .where(Message.dialog_id == dialog_id)
            .order_by(Message.timestamp)
        )
        return result.scalars().all()
