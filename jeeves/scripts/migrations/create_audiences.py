import asyncio
import sys
from pathlib import Path

from sqlalchemy import text

ROOT_DIR = Path(__file__).parent.parent.parent
sys.path.append(str(ROOT_DIR))

from core.db import with_queries

CREATE_ENUM = """
DO $$ BEGIN
    CREATE TYPE audience_status AS ENUM ('new', 'ready', 'error');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;
"""

CREATE_CONTACTS_TABLE = """
CREATE TABLE IF NOT EXISTS contacts (
    id BIGSERIAL PRIMARY KEY,
    telegram_username VARCHAR(255),
    telegram_id BIGINT,
    phone VARCHAR(255),
    is_valid BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
"""

CREATE_AUDIENCES_TABLE = """
CREATE TABLE IF NOT EXISTS audiences (
    id BIGSERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    status audience_status NOT NULL DEFAULT 'new',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
"""

CREATE_AUDIENCES_CONTACTS_TABLE = """
CREATE TABLE IF NOT EXISTS audiences_contacts (
    audience_id BIGINT REFERENCES audiences(id),
    contact_id BIGINT REFERENCES contacts(id),
    PRIMARY KEY (audience_id, contact_id)
);
"""

CREATE_CAMPAIGNS_AUDIENCES_TABLE = """
CREATE TABLE IF NOT EXISTS campaigns_audiences (
    campaign_id BIGINT REFERENCES campaigns(id),
    audience_id BIGINT REFERENCES audiences(id),
    PRIMARY KEY (campaign_id, audience_id)
);
"""

CREATE_USERNAME_INDEX = """
CREATE INDEX IF NOT EXISTS idx_contacts_telegram_username ON contacts(telegram_username);
"""

CREATE_TELEGRAM_ID_INDEX = """
CREATE INDEX IF NOT EXISTS idx_contacts_telegram_id ON contacts(telegram_id);
"""

CREATE_PHONE_INDEX = """
CREATE INDEX IF NOT EXISTS idx_contacts_phone ON contacts(phone);
"""


@with_queries()
async def upgrade(session) -> None:
    """Create audiences and contacts tables."""
    await session.execute(text(CREATE_ENUM))
    print("Created audience_status enum")

    await session.execute(text(CREATE_CONTACTS_TABLE))
    print("Created contacts table")

    await session.execute(text(CREATE_AUDIENCES_TABLE))
    print("Created audiences table")

    await session.execute(text(CREATE_AUDIENCES_CONTACTS_TABLE))
    print("Created audiences_contacts table")

    await session.execute(text(CREATE_CAMPAIGNS_AUDIENCES_TABLE))
    print("Created campaigns_audiences table")

    # Create indexes separately
    await session.execute(text(CREATE_USERNAME_INDEX))
    await session.execute(text(CREATE_TELEGRAM_ID_INDEX))
    await session.execute(text(CREATE_PHONE_INDEX))
    print("Created indexes")


@with_queries()
async def downgrade(session) -> None:
    """Drop audiences and contacts tables."""
    await session.execute(text("DROP TABLE IF EXISTS campaigns_audiences;"))
    print("Dropped campaigns_audiences table")

    await session.execute(text("DROP TABLE IF EXISTS audiences_contacts;"))
    print("Dropped audiences_contacts table")

    await session.execute(text("DROP TABLE IF EXISTS audiences;"))
    print("Dropped audiences table")

    await session.execute(text("DROP TABLE IF EXISTS contacts;"))
    print("Dropped contacts table")

    await session.execute(text("DROP TYPE IF EXISTS audience_status;"))
    print("Dropped audience_status enum")


if __name__ == "__main__":
    if len(sys.argv) != 2 or sys.argv[1] not in ["up", "down"]:
        print("Usage: python -m jeeves.scripts.migrations.create_audiences [up|down]")
        sys.exit(1)

    if sys.argv[1] == "up":
        asyncio.run(upgrade())
    else:
        asyncio.run(downgrade())
