"""Many-to-many association tables."""

from sqlalchemy import Column, ForeignKey, Integer, Table

from .models import Base

# Many-to-many для аккаунтов и кампаний
campaigns_accounts = Table(
    "campaigns_accounts",
    Base.metadata,
    Column("campaign_id", Integer, ForeignKey("campaigns.id"), primary_key=True),
    Column("account_id", Integer, ForeignKey("accounts.id"), primary_key=True),
)

# Many-to-many для кампаний и шаблонов профилей
campaigns_profile_templates = Table(
    "campaigns_profile_templates",
    Base.metadata,
    Column("campaign_id", Integer, ForeignKey("campaigns.id"), primary_key=True),
    Column(
        "profile_template_id",
        Integer,
        ForeignKey("profile_templates.id"),
        primary_key=True,
    ),
)

# Many-to-many для кампаний и аудиторий
campaigns_audiences = Table(
    "campaigns_audiences",
    Base.metadata,
    Column("campaign_id", Integer, ForeignKey("campaigns.id"), primary_key=True),
    Column("audience_id", Integer, ForeignKey("audiences.id"), primary_key=True),
)
