import asyncio
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).parent.parent.parent
sys.path.append(str(ROOT_DIR))

from core.db import with_queries
from sqlalchemy import text

CREATE_COMPANIES_TABLE = """
CREATE TABLE IF NOT EXISTS companies (
    id BIGSERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
"""


@with_queries()
async def upgrade(session) -> None:
    """Create companies table."""
    await session.execute(text(CREATE_COMPANIES_TABLE))
    print("Created companies table")


if __name__ == "__main__":
    asyncio.run(upgrade())
