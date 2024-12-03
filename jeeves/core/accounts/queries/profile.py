"""Profile related queries."""

import logging
from typing import List, Optional, Sequence

from core import db
from core.accounts import models
from sqlalchemy import select
from sqlalchemy.orm import Load

logger = logging.getLogger(__name__)


class ProfileQueries(db.BaseQueries):
    """Queries for profile templates and account profiles."""

    # Core Profile Operations
    @db.decorators.handle_sql_error("get_account_profile")
    async def get_account_profile(
        self, account_id: int
    ) -> Optional[models.AccountProfile]:
        """Get account profile by account ID."""
        result = await self.session.execute(
            select(models.AccountProfile).where(
                models.AccountProfile.account_id == account_id
            )
        )
        return result.scalar_one_or_none()

    @db.decorators.handle_sql_error("create_profile")
    async def create_profile(self, account_id: int) -> Optional[models.AccountProfile]:
        """Create new empty profile for account."""
        profile = self._create_profile_obj(account_id)
        self.session.add(profile)
        await self.session.flush()
        return profile

    @db.decorators.handle_sql_error("apply_template")
    async def apply_template(
        self, account_id: int, template_id: int
    ) -> Optional[models.AccountProfile]:
        """Apply template to account profile."""
        template = await self.session.get(models.ProfileTemplate, template_id)
        if not template or not template.is_active:
            logger.error(f"Template {template_id} not found or inactive")
            return None

        profile = await self.get_account_profile(account_id)
        if not profile:
            profile = self._create_profile_obj(account_id)
            self.session.add(profile)

        self._apply_template_to_profile(profile, template)
        await self.session.flush()

        await self._create_profile_history(profile, template)
        return profile

    # Bulk Profile Operations
    @db.decorators.handle_sql_error("get_all_profiles")
    async def get_all_profiles(
        self, options: Optional[Sequence[Load]] = None
    ) -> List[models.AccountProfile]:
        """Get all account profiles."""
        query = select(models.AccountProfile).order_by(models.AccountProfile.account_id)
        if options:
            for option in options:
                query = query.options(option)
        result = await self.session.execute(query)
        return list(result.scalars().all())

    # Template Operations
    async def create_template(
        self,
        name: str,
        first_name: str,
        last_name: Optional[str] = None,
        bio: Optional[str] = None,
        photo: Optional[bytes] = None,
    ) -> Optional[models.ProfileTemplate]:
        """Create new profile template."""
        template = self._create_template_obj(name, first_name, last_name, bio, photo)
        self.session.add(template)
        await self.session.flush()
        return template

    @db.decorators.handle_sql_error("get_active_templates")
    async def get_active_templates(self) -> List[models.ProfileTemplate]:
        """Get all active profile templates."""
        result = await self.session.execute(
            select(models.ProfileTemplate)
            .where(models.ProfileTemplate.is_active.is_(True))
            .order_by(models.ProfileTemplate.name)
        )
        return list(result.scalars().all())

    @db.decorators.handle_sql_error("delete_template")
    async def delete_template(self, template_id: int) -> bool:
        """Delete profile template."""
        template = await self.session.get(models.ProfileTemplate, template_id)
        if not template:
            return False

        template.is_active = False
        await self.session.flush()
        return True

    @db.decorators.handle_sql_error("update_template")
    async def update_template(self, template_id: int, **updates) -> bool:
        """Update profile template."""
        template = await self.session.get(models.ProfileTemplate, template_id)
        if not template:
            return False

        for key, value in updates.items():
            setattr(template, key, value)

        await self.session.flush()
        return True

    # Factory Methods
    @staticmethod
    def _create_profile_obj(account_id: int) -> models.AccountProfile:
        """Create AccountProfile object."""
        return models.AccountProfile(
            account_id=account_id,
            username="",
            first_name="",
            last_name="",
            bio="",
        )

    @staticmethod
    def _create_template_obj(
        name: str,
        first_name: str,
        last_name: Optional[str] = None,
        bio: Optional[str] = None,
        photo: Optional[bytes] = None,
    ) -> models.ProfileTemplate:
        """Create ProfileTemplate object."""
        return models.ProfileTemplate(
            name=name,
            first_name=first_name,
            last_name=last_name,
            bio=bio,
            photo=photo,
        )

    # Helper Methods
    def _apply_template_to_profile(
        self, profile: models.AccountProfile, template: models.ProfileTemplate
    ) -> None:
        """Apply template data to profile."""
        profile.template_id = template.id
        profile.first_name = template.first_name
        profile.last_name = template.last_name
        profile.bio = template.bio
        profile.photo = template.photo
        profile.is_synced = False

    async def _create_profile_history(
        self, profile: models.AccountProfile, template: models.ProfileTemplate
    ) -> None:
        """Create profile history record."""
        history = models.ProfileHistory(
            profile_id=profile.id,
            template_id=template.id,
            first_name=profile.first_name,
            last_name=profile.last_name,
            bio=profile.bio,
            photo=profile.photo,
            change_type="template_applied",
        )
        self.session.add(history)
        await self.session.flush()
