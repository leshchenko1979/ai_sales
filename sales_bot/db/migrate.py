import asyncio
import sys
from pathlib import Path

# Add the project root to Python path
project_root = str(Path(__file__).parent.parent)
if project_root not in sys.path:
    sys.path.append(project_root)


async def create_tables():
    from config import get_database_url
    from db.models import Base
    from sqlalchemy.ext.asyncio import create_async_engine

    engine = create_async_engine(get_database_url())
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


if __name__ == "__main__":
    asyncio.run(create_tables())
