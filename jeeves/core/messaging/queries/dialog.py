"""Dialog queries."""

import logging
from datetime import datetime, timezone
from typing import Optional

from core.db.base import BaseQueries
from core.messaging.models import Dialog, DialogStatus
from sqlalchemy import select, update
from sqlalchemy.exc import SQLAlchemyError

logger = logging.getLogger(__name__)


class DialogQueries(BaseQueries):
    """Queries for working with dialogs."""

    async def get_dialog(self, username: str, account_id: int) -> Optional[Dialog]:
        """Get dialog by username and account ID."""
        try:
            query = select(Dialog).where(
                Dialog.username == username,
                Dialog.account_id == account_id,
            )
            result = await self.session.execute(query)
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error(f"Failed to get dialog for {username}: {e}")
            return None

    async def get_active_dialog(self, username: str) -> Optional[Dialog]:
        """Get active dialog by username."""
        try:
            query = select(Dialog).where(
                Dialog.username == username,
                Dialog.is_active == True,  # noqa: E712
            )
            result = await self.session.execute(query)
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error(f"Failed to get active dialog for {username}: {e}")
            return None

    async def create_dialog(self, username: str, account_id: int) -> Optional[Dialog]:
        """Create new dialog."""
        try:
            dialog = Dialog(
                username=username,
                account_id=account_id,
                status=DialogStatus.active,
            )
            self.session.add(dialog)
            await self.session.flush()
            return dialog
        except Exception as e:
            logger.error(f"Failed to create dialog for {username}: {e}")
            return None

    async def update_dialog_status(self, dialog_id: int, status: DialogStatus) -> bool:
        """Update dialog status."""
        try:
            await self.session.execute(
                update(Dialog)
                .where(Dialog.id == dialog_id)
                .values(status=status, updated_at=datetime.now(timezone.utc))
            )
            await self.session.flush()
            return True
        except SQLAlchemyError as e:
            logger.error(f"Failed to update dialog status: {e}")
            await self.session.rollback()
            return False

    async def stop_dialog(self, dialog_id: int) -> bool:
        """Stop dialog."""
        try:
            await self.session.execute(
                update(Dialog)
                .where(Dialog.id == dialog_id)
                .values(is_active=False, updated_at=datetime.now(timezone.utc))
            )
            await self.session.flush()
            return True
        except SQLAlchemyError as e:
            logger.error(f"Failed to stop dialog: {e}")
            await self.session.rollback()
            return False
