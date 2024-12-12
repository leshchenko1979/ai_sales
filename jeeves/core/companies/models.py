from datetime import datetime
from enum import Enum
from typing import Optional

from core.db import Base
from sqlalchemy import JSON, Boolean, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func


class CompanyStatus(Enum):
    """Company status enum."""

    active = "active"
    inactive = "inactive"


class Company(Base):
    """Company model."""

    __tablename__ = "companies"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), unique=True)
    descriptions: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    settings: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # Relationships
    campaigns = relationship(
        "Campaign", back_populates="company", cascade="all, delete-orphan"
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    def __str__(self) -> str:
        """String representation."""
        return f"Company(id={self.id}, name={self.name})"
