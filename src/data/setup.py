import logging

from sqlalchemy.ext.asyncio import AsyncEngine

from .tables import Base


async def create_tables(engine: AsyncEngine):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logging.getLogger(__name__).info('Tables created')
