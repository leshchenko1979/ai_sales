import asyncio
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).parent.parent.parent
sys.path.append(str(ROOT_DIR))

from core.db import with_queries
from sqlalchemy import text

CREATE_ENUM = """
-- Create campaign status enum
DO $$ BEGIN
    CREATE TYPE campaign_status AS ENUM ('active', 'inactive');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;
"""

CREATE_CAMPAIGNS_TABLE = """
CREATE TABLE IF NOT EXISTS campaigns (
    id BIGSERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    company_id BIGINT NOT NULL REFERENCES companies(id),
    status campaign_status NOT NULL,
    dialog_engine_type VARCHAR(50) NOT NULL,
    prompt_template TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
"""

CREATE_CAMPAIGNS_ACCOUNTS_TABLE = """
CREATE TABLE IF NOT EXISTS campaigns_accounts (
    campaign_id BIGINT NOT NULL REFERENCES campaigns(id),
    account_id BIGINT NOT NULL REFERENCES accounts(id),
    PRIMARY KEY (campaign_id, account_id)
);
"""

CREATE_CAMPAIGNS_TEMPLATES_TABLE = """
CREATE TABLE IF NOT EXISTS campaigns_profile_templates (
    campaign_id BIGINT NOT NULL REFERENCES campaigns(id),
    profile_template_id BIGINT NOT NULL REFERENCES profile_templates(id),
    PRIMARY KEY (campaign_id, profile_template_id)
);
"""

ALTER_DIALOGS_TABLE = """
ALTER TABLE dialogs
    ADD COLUMN IF NOT EXISTS campaign_id BIGINT REFERENCES campaigns(id);
"""

CREATE_INDEX = """
CREATE INDEX IF NOT EXISTS idx_dialogs_campaign_id ON dialogs(campaign_id);
"""

DROP_INDEX = """
DROP INDEX IF EXISTS idx_dialogs_campaign_id;
"""

DROP_CAMPAIGN_ID = """
ALTER TABLE dialogs DROP COLUMN IF EXISTS campaign_id;
"""

DROP_TABLES = """
DROP TABLE IF EXISTS campaigns_profile_templates;
DROP TABLE IF EXISTS campaigns_accounts;
DROP TABLE IF EXISTS campaigns;
"""

DROP_ENUM = """
DROP TYPE IF EXISTS campaign_status;
"""


@with_queries()
async def upgrade(session) -> None:
    """Create campaign tables."""
    # Create tables in order
    await session.execute(text(CREATE_ENUM))
    await session.execute(text(CREATE_CAMPAIGNS_TABLE))
    await session.execute(text(CREATE_CAMPAIGNS_ACCOUNTS_TABLE))
    await session.execute(text(CREATE_CAMPAIGNS_TEMPLATES_TABLE))
    await session.execute(text(ALTER_DIALOGS_TABLE))
    await session.execute(text(CREATE_INDEX))
    print("Created campaign tables")


@with_queries()
async def downgrade(session) -> None:
    """Drop campaign tables."""
    # Drop in reverse order
    await session.execute(text(DROP_INDEX))
    await session.execute(text(DROP_CAMPAIGN_ID))
    await session.execute(text(DROP_TABLES))
    await session.execute(text(DROP_ENUM))
    print("Dropped campaign tables")


if __name__ == "__main__":
    if len(sys.argv) != 2 or sys.argv[1] not in ["up", "down"]:
        print("Usage: python -m jeeves.scripts.migrations.create_campaigns [up|down]")
        sys.exit(1)

    if sys.argv[1] == "up":
        asyncio.run(upgrade())
    else:
        asyncio.run(downgrade())
