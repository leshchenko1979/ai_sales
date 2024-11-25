from datetime import datetime
from enum import Enum
from typing import Any

from sqlalchemy import BigInteger, Column, DateTime
from sqlalchemy import Enum as SQLEnum
from sqlalchemy import ForeignKey, Index, Integer, String, TypeDecorator
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class EnumType(TypeDecorator):
    """Base class for SQLAlchemy enum handling"""

    impl = SQLEnum
    cache_ok = True

    def __init__(self, enum_class, **kw):
        # Store enum class for later use
        self.enum_class = enum_class
        # Create the enum type with lowercase values
        enum_values = [e.value.lower() for e in enum_class]
        super().__init__(enum_values, **kw)

    def process_bind_param(self, value: Any, dialect: Any) -> str | None:
        """Convert enum to string when saving to DB"""
        if value is None:
            return None
        if isinstance(value, str):
            return value.lower()
        if isinstance(value, self.enum_class):
            return value.value.lower()
        return None

    def process_result_value(self, value: Any, dialect: Any) -> Any:
        """Convert string from DB to enum"""
        if value is None:
            return None
        return self.enum_class.from_string(value)

    def coerce_compared_value(self, op, value):
        """Handle comparison operations"""
        if isinstance(value, str):
            return self
        return super().coerce_compared_value(op, value)


class StrEnum(str, Enum):
    """Base class for string enums with case-insensitive handling"""

    @classmethod
    def from_string(cls, value: str | None) -> "StrEnum | None":
        """Safely convert string to enum value"""
        if value is None:
            return None
        try:
            return cls(value.lower())
        except (ValueError, AttributeError):
            return None

    def _missing_(cls, value: Any) -> "StrEnum | None":
        """Handle case-insensitive lookup"""
        if isinstance(value, str):
            value = value.lower()
            for member in cls:
                if member.value.lower() == value:
                    return member
        return None

    def __str__(self) -> str:
        """Return lowercase string value for database"""
        return self.value.lower()


class AccountStatus(StrEnum):
    """Статусы аккаунтов"""

    ACTIVE = "active"
    DISABLED = "disabled"
    BLOCKED = "blocked"


class DialogStatus(StrEnum):
    """Статусы диалогов"""

    ACTIVE = "active"
    QUALIFIED = "qualified"
    STOPPED = "stopped"
    FAILED = "failed"


class MessageDirection(StrEnum):
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
        EnumType(AccountStatus), nullable=False, default=AccountStatus.ACTIVE
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
    status = Column(EnumType(DialogStatus), nullable=False, default=DialogStatus.ACTIVE)
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
    direction = Column(EnumType(MessageDirection), nullable=False)
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
