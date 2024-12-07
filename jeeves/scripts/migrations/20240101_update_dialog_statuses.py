"""Migration to update dialog statuses."""

import sys
from pathlib import Path

ROOT_DIR = Path(__file__).parent.parent.parent
sys.path.append(str(ROOT_DIR))

from core.db.decorators import with_queries
from sqlalchemy import text


async def update_dialog_status_enum(session):
    """Update dialog status enum type in database."""
    # First check if old type exists
    result = await session.execute(
        text(
            """
        SELECT EXISTS (
            SELECT 1 FROM pg_type WHERE typname = 'dialog_status'
        );
    """
        )
    )
    has_old_type = result.scalar()

    # Create new enum type
    await session.execute(
        text(
            """
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'dialog_status_new') THEN
                CREATE TYPE dialog_status_new AS ENUM (
                    'active',
                    'success',
                    'rejected',
                    'not_qualified',
                    'blocked',
                    'expired',
                    'stopped'
                );
            END IF;
        END$$;
    """
        )
    )

    # Update column to use new enum type
    await session.execute(
        text(
            """
        ALTER TABLE dialogs
        ALTER COLUMN status TYPE dialog_status_new
        USING CASE status::text
            WHEN 'meeting_scheduled' THEN 'success'::dialog_status_new
            WHEN 'closed' THEN 'stopped'::dialog_status_new
            ELSE status::text::dialog_status_new
        END;
    """
        )
    )

    # Drop old type if it exists
    if has_old_type:
        await session.execute(text("DROP TYPE dialog_status;"))

    # Rename new type
    await session.execute(text("ALTER TYPE dialog_status_new RENAME TO dialog_status;"))


@with_queries
async def migrate_dialog_statuses(session):
    """Update dialog statuses to new format."""
    # Update the enum type and migrate data in one transaction
    await update_dialog_status_enum(session)
    await session.commit()


if __name__ == "__main__":
    import asyncio

    asyncio.run(migrate_dialog_statuses())
