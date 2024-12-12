"""Profile related models."""

from datetime import datetime
from typing import TYPE_CHECKING, Annotated, Optional

from core.db.models import Base, TimestampType
from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    LargeBinary,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

if TYPE_CHECKING:
    from .account import Account


DateTimeType = Annotated[
    Optional[datetime], mapped_column(DateTime(timezone=True), nullable=True)
]


class ProfileTemplate(Base):
    """Template for account profiles."""

    __tablename__ = "profile_templates"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    name: Mapped[str] = mapped_column(String, unique=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Profile data
    username: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    first_name: Mapped[str] = mapped_column(String)
    last_name: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    bio: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    photo: Mapped[Optional[bytes]] = mapped_column(LargeBinary, nullable=True)

    # Meta
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    source_account_id: Mapped[Optional[int]] = mapped_column(
        BigInteger, ForeignKey("accounts.id"), nullable=True
    )

    # Timestamps
    created_at: Mapped[TimestampType]
    updated_at: Mapped[TimestampType]

    # Relationships
    profiles: Mapped[list["AccountProfile"]] = relationship(
        "AccountProfile",
        back_populates="template",
        foreign_keys="AccountProfile.template_id",
        cascade="all",
    )
    source_account: Mapped[Optional["Account"]] = relationship(
        "Account", foreign_keys=[source_account_id]
    )

    def __str__(self) -> str:
        """String representation."""
        return f"ProfileTemplate(id={self.id}, name={self.name})"


class AccountProfile(Base):
    """Profile state for account with history tracking."""

    __tablename__ = "account_profiles"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    account_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("accounts.id"), unique=True, index=True
    )
    template_id: Mapped[Optional[int]] = mapped_column(
        BigInteger, ForeignKey("profile_templates.id"), nullable=True, index=True
    )

    # Current profile data from Telegram
    username: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    first_name: Mapped[str] = mapped_column(String)
    last_name: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    bio: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    photo: Mapped[Optional[bytes]] = mapped_column(LargeBinary, nullable=True)

    # Sync status
    is_synced: Mapped[bool] = mapped_column(Boolean, default=False)
    last_synced_at: Mapped[DateTimeType]
    last_telegram_update: Mapped[DateTimeType]

    # Timestamps
    created_at: Mapped[TimestampType]
    updated_at: Mapped[TimestampType]

    # Relationships
    account: Mapped["Account"] = relationship(
        "Account", back_populates="profile", foreign_keys=[account_id]
    )
    template: Mapped[Optional["ProfileTemplate"]] = relationship(
        "ProfileTemplate", foreign_keys=[template_id], back_populates="profiles"
    )
    history: Mapped[list["ProfileHistory"]] = relationship(
        "ProfileHistory",
        back_populates="profile",
        order_by="desc(ProfileHistory.created_at)",
    )

    def __str__(self) -> str:
        """String representation."""
        return f"AccountProfile(id={self.id}, account_id={self.account_id})"

    def update_data(
        self,
        username: Optional[str] = None,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
        bio: Optional[str] = None,
        synced_at: Optional[datetime] = None,
        telegram_update: Optional[datetime] = None,
    ) -> None:
        """Update profile data."""
        self.username = username or ""
        self.first_name = first_name or ""
        self.last_name = last_name or ""
        self.bio = bio or ""
        self.is_synced = True
        if synced_at:
            self.last_synced_at = synced_at
        if telegram_update:
            self.last_telegram_update = telegram_update


class ProfileHistory(Base):
    """History of profile changes."""

    __tablename__ = "profile_history"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    profile_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("account_profiles.id", ondelete="CASCADE"), index=True
    )

    # Profile state at the time
    username: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    first_name: Mapped[str] = mapped_column(String)
    last_name: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    bio: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    photo: Mapped[Optional[bytes]] = mapped_column(LargeBinary, nullable=True)

    # Change metadata
    template_id: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        ForeignKey("profile_templates.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    change_type: Mapped[str] = mapped_column(String)

    # Timestamps
    created_at: Mapped[TimestampType]
    updated_at: Mapped[TimestampType]

    # Relationships
    profile: Mapped["AccountProfile"] = relationship(
        "AccountProfile", back_populates="history", lazy="selectin"
    )
    template: Mapped[Optional["ProfileTemplate"]] = relationship(
        "ProfileTemplate", lazy="selectin"
    )

    def __str__(self) -> str:
        """String representation."""
        return f"ProfileHistory(id={self.id}, profile_id={self.profile_id}, type={self.change_type})"
