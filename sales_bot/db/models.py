from datetime import datetime, timedelta
from enum import Enum

from sqlalchemy import BigInteger, Boolean, Column, DateTime
from sqlalchemy import Enum as SQLAlchemyEnum
from sqlalchemy import ForeignKey, Index, Integer, String, event
from sqlalchemy.orm import declarative_base, relationship, validates

Base = declarative_base()


class AccountStatus(str, Enum):
    """Account statuses"""

    new = "new"
    code_requested = "code_requested"
    password_requested = "password_requested"
    active = "active"
    disabled = "disabled"
    blocked = "blocked"
    warming = "warming"


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
        default=AccountStatus.new,
    )
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_used_at = Column(DateTime, default=datetime.utcnow)
    last_warmup_at = Column(DateTime, nullable=True)
    flood_wait_until = Column(DateTime, nullable=True)
    messages_sent = Column(Integer, default=0, nullable=False)
    is_available = Column(Boolean, default=True, nullable=False)
    warmup_count = Column(Integer, default=0)
    ban_count = Column(Integer, default=0)

    dialogs = relationship("Dialog", back_populates="account")

    @property
    def is_in_flood_wait(self) -> bool:
        """Проверка находится ли аккаунт в режиме флуд-контроля"""
        return (
            self.flood_wait_until is not None
            and self.flood_wait_until > datetime.utcnow()
        )

    @property
    def can_be_used(self) -> bool:
        """Проверка можно ли использовать аккаунт"""
        return (
            self.status == AccountStatus.active
            and self.is_available
            and not self.is_in_flood_wait
        )

    def set_flood_wait(self, seconds: int):
        """Установка времени флуд-контроля"""
        self.flood_wait_until = datetime.utcnow() + timedelta(seconds=seconds)

    def clear_flood_wait(self):
        """Сброс флуд-контроля"""
        self.flood_wait_until = None

    @validates("status")
    def validate_status_transition(self, key, new_status: AccountStatus):
        """Validate status transition"""
        old_status = getattr(self, key, None)

        # Если старый статус не установлен, разрешаем любой статус
        if old_status is None:
            return new_status

        # Разрешаем переход в тот же статус, особенно для 'new'
        if old_status == new_status:
            return new_status

        allowed_transitions = {
            AccountStatus.new: [
                AccountStatus.code_requested,
                AccountStatus.blocked,
                AccountStatus.warming,
            ],
            AccountStatus.code_requested: [
                AccountStatus.new,
                AccountStatus.password_requested,
                AccountStatus.active,
                AccountStatus.blocked,
            ],
            AccountStatus.password_requested: [
                AccountStatus.new,
                AccountStatus.active,
                AccountStatus.blocked,
            ],
            AccountStatus.active: [
                AccountStatus.disabled,
                AccountStatus.blocked,
            ],
            AccountStatus.disabled: [
                AccountStatus.active,
                AccountStatus.blocked,
            ],
            AccountStatus.blocked: [
                AccountStatus.new,
            ],
            AccountStatus.warming: [
                AccountStatus.active,
                AccountStatus.blocked,
            ],
        }

        if new_status not in allowed_transitions.get(old_status, []):
            raise ValueError(
                f"Invalid status transition: {old_status.value} -> {new_status.value}"
            )

        return new_status

    def request_code(self) -> bool:
        """Запрос кода авторизации"""
        if self.status != AccountStatus.new:
            return False
        self.status = AccountStatus.code_requested
        return True

    def request_password(self) -> bool:
        """Запрос пароля 2FA"""
        if self.status != AccountStatus.code_requested:
            return False
        self.status = AccountStatus.password_requested
        return True

    def activate(self, session_string: str) -> bool:
        """Активация аккаунта"""
        if self.status not in [
            AccountStatus.code_requested,
            AccountStatus.password_requested,
        ]:
            return False
        self.status = AccountStatus.active
        self.session_string = session_string
        return True

    def disable(self) -> bool:
        """Отключение аккаунта"""
        if self.status not in [AccountStatus.active]:
            return False
        self.status = AccountStatus.disabled
        return True

    def block(self) -> bool:
        """Блокировка аккаунта"""
        self.status = AccountStatus.blocked
        self.session_string = None
        return True

    def record_message(self):
        """Запись отправленного сообщения"""
        self.messages_sent += 1
        self.last_used_at = datetime.utcnow()

    def record_warmup(self):
        """Запись прогрева аккаунта"""
        self.last_warmup_at = datetime.utcnow()

    def needs_warmup(self) -> bool:
        """
        Определяет, нуждается ли аккаунт в разогреве

        :return: Boolean, указывающий на необходимость разогрева
        """
        # Логика определения необходимости разогрева
        return (
            self.status == AccountStatus.new
            or (self.status == AccountStatus.warming and self.warmup_count < 10)
            or (datetime.utcnow() - self.last_used_at).days
            > 7  # Более 7 дней без использования
        )

    def __repr__(self):
        return f"<Account {self.phone} [{self.status.value}]>"


@event.listens_for(Account, "before_update")
def account_before_update(mapper, connection, target):
    """Обновление updated_at перед каждым изменением"""
    target.updated_at = datetime.utcnow()


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
    Account.messages_sent,
    postgresql_where=Account.status == AccountStatus.active,
)

Index(
    "idx_accounts_warmup",
    Account.status,
    Account.last_warmup_at,
    postgresql_where=Account.status == AccountStatus.active,
)

Index(
    "idx_accounts_last_used",
    Account.status,
    Account.last_used_at,
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
