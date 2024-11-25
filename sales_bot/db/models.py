from datetime import datetime
from enum import Enum

from sqlalchemy import BigInteger, Column, DateTime
from sqlalchemy import Enum as SQLAlchemyEnum
from sqlalchemy import ForeignKey, Index, Integer, String
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class AccountStatus(str, Enum):
    """Account statuses"""

    active = "active"
    disabled = "disabled"
    blocked = "blocked"


class DialogStatus(str, Enum):
    """Dialog statuses"""

    active = "active"
    qualified = "qualified"
    stopped = "stopped"
    failed = "failed"


class MessageDirection(str, Enum):
    """Message directions"""

    in_ = "in"
    out = "out"


class Account(Base):
    """Telegram account model"""

    __tablename__ = "accounts"

    id = Column(BigInteger, primary_key=True)
    phone = Column(String, nullable=False, unique=True)
    session_string = Column(String)
    status = Column(
        SQLAlchemyEnum(AccountStatus, name="accountstatus"),
        nullable=False,
        default=AccountStatus.active,
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
            self.status == AccountStatus.active
            and self.daily_messages < MAX_DAILY_MESSAGES
        )

    def __repr__(self):
        return f"<Account {self.phone} ({self.status})>"


class Dialog(Base):
    """Dialog model with user"""

    __tablename__ = "dialogs"

    id = Column(BigInteger, primary_key=True)
    account_id = Column(BigInteger, ForeignKey("accounts.id"))
    target_username = Column(String, nullable=False)
    status = Column(
        SQLAlchemyEnum(DialogStatus, name="dialogstatus"),
        nullable=False,
        default=DialogStatus.active,
    )
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    account = relationship("Account", back_populates="dialogs")
    messages = relationship(
        "Message", back_populates="dialog", cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<Dialog {self.id} with @{self.target_username}>"


class Message(Base):
    """Message model in dialog"""

    __tablename__ = "messages"

    id = Column(BigInteger, primary_key=True)
    dialog_id = Column(BigInteger, ForeignKey("dialogs.id"))
    direction = Column(
        SQLAlchemyEnum(MessageDirection, name="messagedirection"), nullable=False
    )
    content = Column(String, nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow)

    dialog = relationship("Dialog", back_populates="messages")

    def __repr__(self):
        return f"<Message {self.id} ({self.direction})>"


# Indexes for query optimization
Index(
    "idx_accounts_status_messages",
    Account.status,
    Account.daily_messages,
    postgresql_where=Account.status == AccountStatus.active,
)

Index(
    "idx_accounts_warmup",
    Account.status,
    Account.last_warmup,
    postgresql_where=Account.status == AccountStatus.active,
)

Index(
    "idx_dialogs_status",
    Dialog.status,
    postgresql_where=Dialog.status == DialogStatus.active,
)

Index("idx_messages_dialog_time", Message.dialog_id, Message.timestamp)

# Export all models
__all__ = [
    "Base",
    "Account",
    "AccountStatus",
    "Dialog",
    "DialogStatus",
    "Message",
    "MessageDirection",
]
