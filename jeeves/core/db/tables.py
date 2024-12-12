"""Database association tables and relationships.

This module defines all many-to-many relationships between models to avoid
circular imports between model modules.
"""

from sqlalchemy import Column, ForeignKey, Integer, Table
from sqlalchemy.orm import relationship

from .models import Base

# Many-to-many association tables
campaigns_accounts = Table(
    "campaigns_accounts",
    Base.metadata,
    Column(
        "campaign_id",
        Integer,
        ForeignKey("campaigns.id", ondelete="CASCADE"),
        primary_key=True,
        index=True,
    ),
    Column(
        "account_id",
        Integer,
        ForeignKey("accounts.id", ondelete="CASCADE"),
        primary_key=True,
        index=True,
    ),
)

campaigns_profile_templates = Table(
    "campaigns_profile_templates",
    Base.metadata,
    Column(
        "campaign_id",
        Integer,
        ForeignKey("campaigns.id", ondelete="CASCADE"),
        primary_key=True,
        index=True,
    ),
    Column(
        "profile_template_id",
        Integer,
        ForeignKey("profile_templates.id", ondelete="CASCADE"),
        primary_key=True,
        index=True,
    ),
)

campaigns_audiences = Table(
    "campaigns_audiences",
    Base.metadata,
    Column(
        "campaign_id",
        Integer,
        ForeignKey("campaigns.id", ondelete="CASCADE"),
        primary_key=True,
        index=True,
    ),
    Column(
        "audience_id",
        Integer,
        ForeignKey("audiences.id", ondelete="CASCADE"),
        primary_key=True,
        index=True,
    ),
)


# Relationship definitions
def setup_relationships():
    """Set up relationships between models to avoid circular imports."""
    from core.accounts.models import Account
    from core.accounts.models.profile import ProfileTemplate
    from core.audiences.models import Audience
    from core.campaigns.models import Campaign

    # Campaign relationships
    Campaign.accounts = relationship(
        "Account",
        secondary=campaigns_accounts,
        back_populates="campaigns",
        cascade="save-update",  # Only cascade saves and updates, not deletes
        passive_deletes=True,  # Let the database handle cascade deletes
    )
    Campaign.profile_templates = relationship(
        "ProfileTemplate",
        secondary=campaigns_profile_templates,
        back_populates="campaigns",
        cascade="save-update",
        passive_deletes=True,
    )
    Campaign.audiences = relationship(
        "Audience",
        secondary=campaigns_audiences,
        back_populates="campaigns",
        cascade="save-update",
        passive_deletes=True,
    )

    # Account relationships
    Account.campaigns = relationship(
        "Campaign",
        secondary=campaigns_accounts,
        back_populates="accounts",
        cascade="save-update",  # Only cascade saves and updates, not deletes
        passive_deletes=True,  # Let the database handle cascade deletes
    )

    # ProfileTemplate relationships
    ProfileTemplate.campaigns = relationship(
        "Campaign",
        secondary=campaigns_profile_templates,
        back_populates="profile_templates",
        cascade="save-update",
        passive_deletes=True,
    )

    # Audience relationships
    Audience.campaigns = relationship(
        "Campaign",
        secondary=campaigns_audiences,
        back_populates="audiences",
        cascade="save-update",
        passive_deletes=True,
    )
