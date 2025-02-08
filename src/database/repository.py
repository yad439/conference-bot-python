import automapper  # type: ignore
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.orm import selectinload

from dto import SpeechDto

from .tables import Speech


class SpeechRepository:
    def __init__(self, factory: async_sessionmaker[AsyncSession]) -> None:
        self._factory = factory
        self._mapper = automapper.mapper.to(SpeechDto)

    async def get_all(self):
        statement = select(Speech).options(selectinload(Speech.time_slot))
        async with self._factory() as session:
            result = await session.execute(statement)
            return list(map(self._mapper.map, result.scalars().all()))
