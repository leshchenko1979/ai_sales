"""Account model."""

from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import TYPE_CHECKING, Annotated, Optional

from core.db.models import Base, TimestampType
from infrastructure.config import MAX_MESSAGES_PER_DAY, MAX_MESSAGES_PER_HOUR
from sqlalchemy import BigInteger, Boolean, DateTime
from sqlalchemy import Enum as SQLEnum
from sqlalchemy import Integer, String, event
from sqlalchemy.orm import Mapped, mapped_column, relationship
from utils.phone import normalize_phone

if TYPE_CHECKING:
    from core.messaging.models import Dialog

    from .profile import AccountProfile


class AccountStatus(str, Enum):
    """Account status enum."""

    new = "new"
    code_requested = "code_requested"
    password_requested = "password_requested"
    active = "active"
    disabled = "disabled"
    blocked = "blocked"
    warming = "warming"


DateTimeType = Annotated[
    Optional[datetime], mapped_column(DateTime(timezone=True), nullable=True)
]


class Account(Base):
    """Telegram account model."""

    __tablename__ = "accounts"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    phone: Mapped[str] = mapped_column(String, unique=True)
    session_string: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    status: Mapped[AccountStatus] = mapped_column(
        SQLEnum(AccountStatus), default=AccountStatus.new
    )

    # Usage tracking
    messages_sent: Mapped[int] = mapped_column(Integer, default=0)
    daily_messages: Mapped[int] = mapped_column(Integer, default=0)
    is_available: Mapped[bool] = mapped_column(Boolean, default=True)

    # Timestamps
    created_at: Mapped[TimestampType]
    updated_at: Mapped[TimestampType]
    last_used_at: Mapped[DateTimeType]
    last_warmup_at: Mapped[DateTimeType]
    flood_wait_until: Mapped[DateTimeType]

    # Relationships
    dialogs: Mapped[list["Dialog"]] = relationship(
        "Dialog",
        back_populates="account",
        lazy="selectin",
        cascade="all, delete-orphan",
    )
    profile: Mapped[Optional["AccountProfile"]] = relationship(
        "AccountProfile",
        back_populates="account",
        uselist=False,
        lazy="selectin",
        cascade="all, delete-orphan",
    )

    # Note: campaigns relationship is defined in core.db.tables to avoid circular imports

    def __init__(self, **kwargs):
        """Initialize account with normalized phone number."""
        if "phone" in kwargs:
            kwargs["phone"] = normalize_phone(kwargs["phone"])
        super().__init__(**kwargs)

    @property
    def is_in_flood_wait(self) -> bool:
        """Check if account is in flood wait."""
        if not self.flood_wait_until:
            return False
        return self.flood_wait_until > datetime.now(timezone.utc)

    @property
    def can_be_used(self) -> bool:
        """Check if account can be used."""
        return (
            self.status == AccountStatus.active
            and self.is_available
            and not self.is_in_flood_wait
            and not self.is_daily_limit_reached
            and not self.is_hourly_limit_reached
        )

    @property
    def is_daily_limit_reached(self) -> bool:
        """Check if daily message limit is reached."""
        return self.daily_messages >= MAX_MESSAGES_PER_DAY

    @property
    def is_hourly_limit_reached(self) -> bool:
        """Check if hourly message limit is reached."""
        if not self.last_used_at:
            return False

        hour_ago = datetime.now(timezone.utc) - timedelta(hours=1)
        if self.last_used_at <= hour_ago:
            return False

        return self.daily_messages >= MAX_MESSAGES_PER_HOUR

    def __str__(self) -> str:
        """String representation."""
        return (
            f"Account(id={self.id}, phone={self.phone}, "
            f"status={self.status.value}, messages={self.daily_messages})"
        )


@event.listens_for(Account, "before_insert")
@event.listens_for(Account, "before_update")
def normalize_account_phone(mapper, connection, target):
    """Normalize phone number before saving to database."""
    if hasattr(target, "phone") and target.phone:
        target.phone = normalize_phone(target.phone)
