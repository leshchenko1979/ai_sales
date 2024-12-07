from datetime import datetime
from enum import Enum
from typing import List, Optional

from core.campaigns.models import Campaign
from core.db import Base
from core.db.tables import campaigns_audiences
from sqlalchemy import BigInteger, Boolean, Column, DateTime
from sqlalchemy import Enum as SQLEnum
from sqlalchemy import ForeignKey, String, Table, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func


class AudienceStatus(str, Enum):
    """Audience status enum."""

    new = "new"
    ready = "ready"
    error = "error"


# Many-to-many для контактов
audiences_contacts = Table(
    "audiences_contacts",
    Base.metadata,
    Column("audience_id", BigInteger, ForeignKey("audiences.id"), primary_key=True),
    Column("contact_id", BigInteger, ForeignKey("contacts.id"), primary_key=True),
)


class Contact(Base):
    """Contact model."""

    __tablename__ = "contacts"

    id: Mapped[int] = mapped_column(primary_key=True)
    telegram_username: Mapped[Optional[str]] = mapped_column(String(255))
    telegram_id: Mapped[Optional[int]] = mapped_column(BigInteger)
    phone: Mapped[Optional[str]] = mapped_column(String(255))
    is_valid: Mapped[bool] = mapped_column(Boolean, default=True)

    # Связи
    audiences: Mapped[List["Audience"]] = relationship(
        secondary=audiences_contacts, back_populates="contacts", lazy="selectin"
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class Audience(Base):
    """Audience model."""

    __tablename__ = "audiences"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[Optional[str]] = mapped_column(Text)
    status: Mapped[AudienceStatus] = mapped_column(
        SQLEnum(AudienceStatus, name="audience_status")
    )

    # Связи
    contacts: Mapped[List[Contact]] = relationship(
        secondary=audiences_contacts, back_populates="audiences", lazy="noload"
    )
    campaigns: Mapped[List["Campaign"]] = relationship(
        "Campaign",
        secondary=campaigns_audiences,
        back_populates="audiences",
        lazy="noload",
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    @property
    def total_contacts(self) -> int:
        """Get total number of contacts in audience."""
        return len(self.contacts)
