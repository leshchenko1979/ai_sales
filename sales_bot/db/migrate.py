import asyncio

from config import get_database_url
from db.models import Base
from sqlalchemy.ext.asyncio import create_async_engine


async def create_tables():
    engine = create_async_engine(get_database_url())
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


if __name__ == "__main__":
    asyncio.run(create_tables())
