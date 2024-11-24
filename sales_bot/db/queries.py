import logging
import os
from contextlib import asynccontextmanager
from datetime import datetime
from typing import List, Optional

from config import DATABASE_URL
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from .models import (
    Account,
    AccountStatus,
    Dialog,
    DialogStatus,
    Message,
    MessageDirection,
)

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
        try:
            result = await self.session.execute(
                select(Account).where(Account.phone == phone)
            )
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error(f"Error getting account by phone {phone}: {e}", exc_info=True)
            return None

    async def get_account_by_id(self, account_id: int) -> Optional[Account]:
        """Get account by ID"""
        try:
            return await self.session.get(Account, account_id)
        except Exception as e:
            logger.error(
                f"Error getting account by ID {account_id}: {e}", exc_info=True
            )
            return None

    async def get_active_accounts(self) -> List[Account]:
        """Get all active accounts ordered by message count"""
        result = await self.session.execute(
            select(Account)
            .where(Account.status == AccountStatus.active)
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
            select(Account).where(Account.status == AccountStatus.active)
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

    async def update_account_status(
        self, account_id: int, status: AccountStatus
    ) -> bool:
        """Update account status"""
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

    async def create_account(self, phone_number: str) -> Account:
        # Проверка существования аккаунта
        existing_account = await self.session.execute(
            select(Account).filter_by(phone=phone_number)
        )
        existing_account = existing_account.scalar_one_or_none()

        if existing_account:
            raise ValueError(f"Account with phone number {phone_number} already exists")

        # Создание нового аккаунта
        new_account = Account(
            phone=phone_number,
            status=AccountStatus.new,  # Начальный статус
            last_used_at=datetime.utcnow(),  # Установка текущего времени
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

    async def update_session(self, account_id: int, session_string: str) -> bool:
        """Update account session string"""
        try:
            account = await self.session.get(Account, account_id)
            if not account:
                return False

            account.session_string = session_string
            account.status = AccountStatus.active
            account.last_used_at = datetime.utcnow()

            self.session.add(account)
            return True

        except Exception as e:
            logger.error(f"Database error: {e}", exc_info=True)
            return False

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

    async def get_all_accounts(self) -> List[Account]:
        """Get all accounts regardless of their status"""
        async with get_db() as session:
            query = select(Account)
            result = await session.execute(query)
            return list(result.scalars().all())


class DialogQueries:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_dialog(self, username: str, account_id: int) -> Optional[Dialog]:
        """Create new dialog"""
        try:
            dialog = Dialog(
                target_username=username,
                account_id=account_id,
                status=DialogStatus.active,
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
            select(Dialog).where(Dialog.status == DialogStatus.active)
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

    async def save_message(
        self, dialog_id: int, direction: MessageDirection, content: str
    ):
        """Save message"""
        try:
            message = Message(dialog_id=dialog_id, direction=direction, content=content)
            self.session.add(message)
            await self.session.commit()
            return True
        except Exception as e:
            await self.session.rollback()
            logger.error(f"Error saving message: {e}", exc_info=True)
            raise

    async def get_all_dialogs(self) -> list[Dialog]:
        """Get all dialogs from the database"""
        async with get_db() as session:
            query = select(Dialog).order_by(Dialog.created_at.desc())
            result = await session.execute(query)
            return list(result.scalars().all())
