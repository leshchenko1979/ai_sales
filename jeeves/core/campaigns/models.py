from datetime import datetime

from core.db import Base
from sqlalchemy import Boolean, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func


class Campaign(Base):
    """Campaign model."""

    __tablename__ = "campaigns"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # Dialog strategy type (e.g. "cold_meetings", etc)
    dialog_strategy: Mapped[str] = mapped_column(String(50))

    # Direct relationships (not many-to-many)
    dialogs = relationship(
        "Dialog", back_populates="campaign", cascade="all, delete-orphan"
    )
    company = relationship("Company", back_populates="campaigns")

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
