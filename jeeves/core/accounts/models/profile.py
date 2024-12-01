"""Profile related models."""

from datetime import datetime
from typing import TYPE_CHECKING, List, Optional

from core.db.models import Base
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

    # Relationships
    profiles: Mapped[List["AccountProfile"]] = relationship(
        "AccountProfile",
        back_populates="template",
        foreign_keys="AccountProfile.template_id",
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
        BigInteger, ForeignKey("accounts.id"), unique=True
    )
    template_id: Mapped[Optional[int]] = mapped_column(
        BigInteger, ForeignKey("profile_templates.id"), nullable=True
    )

    # Current profile data from Telegram
    username: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    first_name: Mapped[str] = mapped_column(String)
    last_name: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    bio: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    photo: Mapped[Optional[bytes]] = mapped_column(LargeBinary, nullable=True)

    # Sync status
    is_synced: Mapped[bool] = mapped_column(Boolean, default=False)
    last_synced_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    last_telegram_update: Mapped[Optional[datetime]] = mapped_column(
        DateTime, nullable=True
    )

    # Relationships
    account: Mapped["Account"] = relationship(
        "Account", back_populates="profile", foreign_keys=[account_id]
    )
    template: Mapped[Optional["ProfileTemplate"]] = relationship(
        "ProfileTemplate", foreign_keys=[template_id], back_populates="profiles"
    )
    history: Mapped[List["ProfileHistory"]] = relationship(
        "ProfileHistory",
        back_populates="profile",
        order_by="desc(ProfileHistory.created_at)",
    )

    def __str__(self) -> str:
        """String representation."""
        return f"AccountProfile(id={self.id}, account_id={self.account_id})"


class ProfileHistory(Base):
    """History of profile changes."""

    __tablename__ = "profile_history"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    profile_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("account_profiles.id")
    )

    # Profile state at the time
    username: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    first_name: Mapped[str] = mapped_column(String)
    last_name: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    bio: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    photo: Mapped[Optional[bytes]] = mapped_column(LargeBinary, nullable=True)

    # Change metadata
    template_id: Mapped[Optional[int]] = mapped_column(
        BigInteger, ForeignKey("profile_templates.id"), nullable=True
    )
    change_type: Mapped[str] = mapped_column(
        String
    )  # template_applied, manual_update, telegram_sync

    # Relationships
    profile: Mapped["AccountProfile"] = relationship(
        "AccountProfile", back_populates="history"
    )
    template: Mapped[Optional["ProfileTemplate"]] = relationship("ProfileTemplate")

    def __str__(self) -> str:
        """String representation."""
        return f"ProfileHistory(id={self.id}, profile_id={self.profile_id}, type={self.change_type})"
