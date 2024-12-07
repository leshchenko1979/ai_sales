from datetime import datetime
from enum import Enum
from typing import List

from core.audiences.models import Audience
from core.db import Base
from core.db.tables import (
    campaigns_accounts,
    campaigns_audiences,
    campaigns_profile_templates,
)
from sqlalchemy import DateTime
from sqlalchemy import Enum as SQLAEnum
from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func


class CampaignStatus(Enum):
    active = "active"
    inactive = "inactive"


class Campaign(Base):
    """Campaign model."""

    __tablename__ = "campaigns"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"))
    status: Mapped[CampaignStatus] = mapped_column(SQLAEnum(CampaignStatus))

    # Тип диалогового движка (например, "cold_sales", "survey", etc)
    dialog_engine_type: Mapped[str] = mapped_column(String(50))

    # Шаблон промпта для этой кампании
    prompt_template: Mapped[str] = mapped_column(String)

    # Связи
    accounts = relationship(
        "Account", secondary=campaigns_accounts, back_populates="campaigns"
    )
    profile_templates = relationship(
        "ProfileTemplate", secondary=campaigns_profile_templates, lazy="selectin"
    )
    dialogs = relationship("Dialog", back_populates="campaign")
    audiences: Mapped[List["Audience"]] = relationship(
        secondary=campaigns_audiences, back_populates="campaigns", lazy="selectin"
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
