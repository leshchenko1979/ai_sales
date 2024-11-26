"""Database models."""

from datetime import datetime

from sqlalchemy import DateTime, event
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Base class for all models."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )


@event.listens_for(Base, "before_update", propagate=True)
def timestamp_before_update(mapper, connection, target):
    """Update timestamp before update."""
    target.updated_at = datetime.utcnow()
