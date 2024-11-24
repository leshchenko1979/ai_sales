from datetime import datetime
from enum import Enum

from sqlalchemy import BigInteger, Column, DateTime
from sqlalchemy import Enum as SQLEnum
from sqlalchemy import ForeignKey, Index, Integer, String
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

Base = declarative_base()


class AccountStatus(str, Enum):
    """Статусы аккаунтов"""

    ACTIVE = "active"
    DISABLED = "disabled"
    BLOCKED = "blocked"


class DialogStatus(str, Enum):
    """Статусы диалогов"""

    ACTIVE = "active"
    QUALIFIED = "qualified"
    STOPPED = "stopped"
    FAILED = "failed"


class MessageDirection(str, Enum):
    """Направления сообщений"""

    IN = "in"
    OUT = "out"


class Account(Base):
    """Модель аккаунта Telegram"""

    __tablename__ = "accounts"

    id = Column(BigInteger, primary_key=True)
    phone = Column(String, nullable=False, unique=True)
    session_string = Column(String)
    status = Column(
        SQLEnum(AccountStatus), nullable=False, default=AccountStatus.ACTIVE
    )
    last_used = Column(DateTime)
    last_warmup = Column(DateTime)
    daily_messages = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    dialogs = relationship("Dialog", back_populates="account")

    @property
    def is_available(self) -> bool:
        """Check if account can be used for sending messages"""
        from config import MAX_DAILY_MESSAGES

        return (
            self.status == AccountStatus.ACTIVE
            and self.daily_messages < MAX_DAILY_MESSAGES
        )

    def __repr__(self):
        return f"<Account {self.phone} ({self.status.value})>"


class Dialog(Base):
    """Модель диалога с пользователем"""

    __tablename__ = "dialogs"

    id = Column(BigInteger, primary_key=True)
    account_id = Column(BigInteger, ForeignKey("accounts.id"))
    target_username = Column(String, nullable=False)
    status = Column(SQLEnum(DialogStatus), nullable=False, default=DialogStatus.ACTIVE)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    account = relationship("Account", back_populates="dialogs")
    messages = relationship(
        "Message", back_populates="dialog", cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<Dialog {self.id} with @{self.target_username}>"


class Message(Base):
    """Модель сообщения в диалоге"""

    __tablename__ = "messages"

    id = Column(BigInteger, primary_key=True)
    dialog_id = Column(BigInteger, ForeignKey("dialogs.id"))
    direction = Column(SQLEnum(MessageDirection), nullable=False)
    content = Column(String, nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow)

    dialog = relationship("Dialog", back_populates="messages")

    def __repr__(self):
        return f"<Message {self.id} ({self.direction.value})>"


# Индексы для оптимизации запросов
Index(
    "idx_accounts_status_messages",
    Account.status,
    Account.daily_messages,
    postgresql_where=Account.status == AccountStatus.ACTIVE,
)

Index(
    "idx_accounts_warmup",
    Account.status,
    Account.last_warmup,
    postgresql_where=Account.status == AccountStatus.ACTIVE,
)

Index(
    "idx_dialogs_status",
    Dialog.status,
    postgresql_where=Dialog.status == DialogStatus.ACTIVE,
)

Index("idx_messages_dialog_time", Message.dialog_id, Message.timestamp)

# Экспортируем все модели
__all__ = [
    "Base",
    "Account",
    "AccountStatus",
    "Dialog",
    "DialogStatus",
    "Message",
    "MessageDirection",
]
