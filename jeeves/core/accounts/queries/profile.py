"""Profile related queries."""

import logging
from typing import List, Optional

from core.accounts.models.profile import AccountProfile, ProfileHistory, ProfileTemplate
from core.db import BaseQueries
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

logger = logging.getLogger(__name__)


class ProfileQueries(BaseQueries):
    """Queries for profile templates and account profiles."""

    async def get_account_profile(self, account_id: int) -> Optional[AccountProfile]:
        """Get account profile by account ID."""
        try:
            result = await self.session.execute(
                select(AccountProfile).where(AccountProfile.account_id == account_id)
            )
            return result.scalar_one_or_none()
        except SQLAlchemyError as e:
            logger.error(f"Failed to get profile for account {account_id}: {e}")
            return None

    async def create_template(
        self,
        name: str,
        first_name: str,
        last_name: Optional[str] = None,
        bio: Optional[str] = None,
        photo_path: Optional[str] = None,
    ) -> Optional[ProfileTemplate]:
        """Create new profile template."""
        try:
            template = ProfileTemplate(
                name=name,
                first_name=first_name,
                last_name=last_name,
                bio=bio,
                photo_path=photo_path,
            )
            self.session.add(template)
            await self.session.flush()
            return template
        except IntegrityError:
            logger.error(f"Template with name {name} already exists")
            await self.session.rollback()
            return None
        except SQLAlchemyError as e:
            logger.error(f"Failed to create template {name}: {e}")
            await self.session.rollback()
            return None

    async def get_active_templates(self) -> List[ProfileTemplate]:
        """Get all active profile templates."""
        try:
            result = await self.session.execute(
                select(ProfileTemplate)
                .where(ProfileTemplate.is_active.is_(True))
                .order_by(ProfileTemplate.name)
            )
            return list(result.scalars().all())
        except SQLAlchemyError as e:
            logger.error(f"Failed to get active templates: {e}")
            return []

    async def apply_template(
        self, account_id: int, template_id: int
    ) -> Optional[AccountProfile]:
        """Apply template to account profile."""
        try:
            # Get template and profile in a single transaction
            template = await self.session.get(ProfileTemplate, template_id)
            if not template or not template.is_active:
                logger.error(f"Template {template_id} not found or inactive")
                return None

            profile = await self.get_account_profile(account_id)
            if not profile:
                profile = AccountProfile(account_id=account_id)

            # Copy template data
            profile.template_id = template.id
            profile.first_name = template.first_name
            profile.last_name = template.last_name
            profile.bio = template.bio
            profile.photo_path = template.photo_path
            profile.is_synced = False

            self.session.add(profile)
            await self.session.flush()

            # Create history record
            history = ProfileHistory(
                profile_id=profile.id,
                template_id=template.id,
                first_name=profile.first_name,
                last_name=profile.last_name,
                bio=profile.bio,
                photo_path=profile.photo_path,
                change_type="template_applied",
            )
            self.session.add(history)
            await self.session.flush()

            return profile

        except SQLAlchemyError as e:
            logger.error(
                f"Failed to apply template {template_id} to account {account_id}: {e}"
            )
            await self.session.rollback()
            return None
