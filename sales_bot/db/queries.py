import os
from datetime import datetime, timedelta
from typing import AsyncGenerator, List, Optional

from config import DATABASE_URL
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.future import select
from sqlalchemy.orm import sessionmaker

from .models import Account, AccountStatus, Base, Dialog, Message

# Update the DATABASE_URL to use asyncpg
DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://")

# Создаем асинхронный движок базы данных
engine = create_async_engine(DATABASE_URL) if not os.getenv("TESTING") else None

# Создаем фабрику асинхронных сессий
AsyncSessionLocal = (
    sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    if not os.getenv("TESTING")
    else None
)


async def init_db():
    """Инициализация базы данных"""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Получение сессии базы данных"""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


class AccountQueries:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_account(self, phone: str) -> Optional[Account]:
        """Create new account"""
        account = Account(phone=phone, status=AccountStatus.ACTIVE, daily_messages=0)
        self.session.add(account)
        await self.session.commit()
        await self.session.refresh(account)
        return account

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

    async def get_all_accounts(self) -> List[Account]:
        """Get all accounts"""
        result = await self.session.execute(
            select(Account).order_by(Account.status, Account.daily_messages)
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
        """Get accounts that need warmup"""
        week_ago = datetime.now() - timedelta(days=7)
        result = await self.session.execute(
            select(Account)
            .where(Account.status == AccountStatus.ACTIVE)
            .where((Account.last_warmup == None) | (Account.last_warmup < week_ago))
            .order_by(Account.last_warmup.nulls_first())
            .limit(5)
        )
        return result.scalars().all()

    async def update_session(self, account_id: int, session_string: str) -> bool:
        """Update account session string"""
        result = await self.session.execute(
            update(Account)
            .where(Account.id == account_id)
            .values(session_string=session_string)
        )
        await self.session.commit()
        return result.rowcount > 0

    async def update_account_status(self, phone: str, status: AccountStatus) -> bool:
        """Update account status"""
        result = await self.session.execute(
            update(Account).where(Account.phone == phone).values(status=status)
        )
        await self.session.commit()
        return result.rowcount > 0

    async def update_account_status_by_id(
        self, account_id: int, status: AccountStatus
    ) -> bool:
        """Update account status by ID"""
        result = await self.session.execute(
            update(Account).where(Account.id == account_id).values(status=status)
        )
        await self.session.commit()
        return result.rowcount > 0

    async def increment_messages(self, account_id: int) -> bool:
        """Increment daily message counter"""
        result = await self.session.execute(
            update(Account)
            .where(Account.id == account_id)
            .values(daily_messages=Account.daily_messages + 1, last_used=datetime.now())
        )
        await self.session.commit()
        return result.rowcount > 0

    async def reset_daily_messages(self) -> bool:
        """Reset daily message counters for all accounts"""
        result = await self.session.execute(
            update(Account).where(Account.daily_messages > 0).values(daily_messages=0)
        )
        await self.session.commit()
        return result.rowcount > 0

    async def update_account_warmup_time(self, account_id: int) -> bool:
        """Update account warmup timestamp"""
        result = await self.session.execute(
            update(Account)
            .where(Account.id == account_id)
            .values(last_warmup=datetime.now())
        )
        await self.session.commit()
        return result.rowcount > 0


class DialogQueries:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_dialog(self, username: str, account_id: int) -> Dialog:
        """Create new dialog"""
        dialog = Dialog(
            target_username=username, account_id=account_id, status="active"
        )
        self.session.add(dialog)
        await self.session.commit()
        await self.session.refresh(dialog)
        return dialog

    async def get_active_dialog(self, username: str) -> Optional[Dialog]:
        """Get active dialog with user"""
        result = await self.session.execute(
            select(Dialog).where(
                Dialog.target_username == username, Dialog.status == "active"
            )
        )
        return result.scalar_one_or_none()

    async def get_dialog_history(self, dialog_id: int) -> List[Message]:
        """Get dialog history"""
        result = await self.session.execute(
            select(Message)
            .where(Message.dialog_id == dialog_id)
            .order_by(Message.timestamp)
        )
        return result.scalars().all()

    async def save_message(
        self, dialog_id: int, direction: str, content: str
    ) -> Message:
        """Save message"""
        message = Message(dialog_id=dialog_id, direction=direction, content=content)
        self.session.add(message)
        await self.session.commit()
        await self.session.refresh(message)
        return message

    async def update_dialog_status(self, dialog_id: int, status: str) -> bool:
        """Update dialog status"""
        result = await self.session.execute(
            update(Dialog).where(Dialog.id == dialog_id).values(status=status)
        )
        await self.session.commit()
        return result.rowcount > 0
