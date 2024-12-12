"""Database models for messages."""

from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING, Annotated, Optional

from core.db.models import Base, TimestampType, utcnow
from core.messaging.enums import DialogStatus, MessageDirection
from sqlalchemy import BigInteger, DateTime
from sqlalchemy import Enum as SQLEnum
from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

if TYPE_CHECKING:
    from core.accounts.models.account import Account
    from core.campaigns.models import Campaign


DateTimeType = Annotated[
    Optional[datetime], mapped_column(DateTime(timezone=True), nullable=True)
]


class Dialog(Base):
    """Dialog model."""

    __tablename__ = "dialogs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    username: Mapped[str] = mapped_column(String)
    account_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("accounts.id"), index=True
    )
    campaign_id: Mapped[Optional[int]] = mapped_column(
        BigInteger, ForeignKey("campaigns.id"), nullable=True, index=True
    )
    last_message_at: Mapped[DateTimeType]
    is_active: Mapped[bool] = mapped_column(default=True)
    status: Mapped[DialogStatus] = mapped_column(
        SQLEnum(DialogStatus), default=DialogStatus.active
    )

    # Timestamps
    created_at: Mapped[TimestampType]
    updated_at: Mapped[TimestampType]

    # Relationships
    messages: Mapped[list["Message"]] = relationship(
        "Message",
        back_populates="dialog",
        lazy="selectin",
        order_by="Message.timestamp",
        cascade="all, delete-orphan",
    )
    account: Mapped["Account"] = relationship(
        "Account", back_populates="dialogs", lazy="selectin"
    )
    campaign: Mapped["Campaign"] = relationship(
        "Campaign", back_populates="dialogs", lazy="selectin"
    )

    @property
    def last_message(self) -> Optional["Message"]:
        """Get last message in dialog."""
        return self.messages[-1] if self.messages else None

    @property
    def message_count(self) -> int:
        """Get total number of messages in dialog."""
        return len(self.messages)

    def __str__(self) -> str:
        """String representation."""
        return (
            f"Dialog(id={self.id}, username={self.username}, "
            f"messages={self.message_count})"
        )


class Message(Base):
    """Message model."""

    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    dialog_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("dialogs.id"), index=True
    )
    direction: Mapped[MessageDirection] = mapped_column(SQLEnum(MessageDirection))
    content: Mapped[str] = mapped_column(String)
    timestamp: Mapped[TimestampType] = mapped_column(default=utcnow)

    # Timestamps
    created_at: Mapped[TimestampType]
    updated_at: Mapped[TimestampType]

    # Relationships
    dialog: Mapped[Dialog] = relationship(
        Dialog, back_populates="messages", lazy="selectin"
    )

    def __str__(self) -> str:
        """String representation."""
        direction = "→" if self.direction == MessageDirection.OUTGOING else "←"
        return f"[{self.timestamp}] {direction} {self.content}"


@dataclass
class DeliveryOptions:
    """Message delivery options."""

    typing_delay: float = 3.0  # seconds
    message_delay: float = 1.0  # seconds
    simulate_typing: bool = True


@dataclass
class DeliveryResult:
    """Result of message delivery attempt."""

    success: bool
    error: Optional[str] = None
