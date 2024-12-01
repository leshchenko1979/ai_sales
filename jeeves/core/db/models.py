"""Database models."""

from datetime import datetime, timezone
from typing import Annotated

from sqlalchemy import DateTime, event
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def utcnow() -> datetime:
    """Get current UTC datetime with timezone info."""
    return datetime.now(timezone.utc)


TimestampType = Annotated[
    datetime, mapped_column(DateTime(timezone=True), nullable=False)
]


class Base(DeclarativeBase):
    """Base class for all models."""

    created_at: Mapped[TimestampType] = mapped_column(default=utcnow)
    updated_at: Mapped[TimestampType] = mapped_column(default=utcnow)


@event.listens_for(Base, "before_update", propagate=True)
def timestamp_before_update(mapper, connection, target):
    """Update timestamp before update."""
    target.updated_at = utcnow()
