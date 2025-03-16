import datetime
import automapper  # type: ignore
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.orm import contains_eager

from dto import SpeechDto, TimeSlotDto

from .tables import Selection, Speech, TimeSlot


class Repository:
    def __init__(self, factory: async_sessionmaker[AsyncSession]) -> None:
        self._factory = factory
        self._mapper = automapper.mapper.to(SpeechDto)
        self._slot_mapper = automapper.mapper.to(TimeSlotDto)

    def get_session(self):
        return self._factory()

    async def get_all_speeches(self):
        statement = (select(Speech).join(Speech.time_slot)
                     .order_by(TimeSlot.date, Speech.location, TimeSlot.start_time)
                     .options(contains_eager(Speech.time_slot)))
        async with self._factory() as session:
            result = await session.scalars(statement)
            return list(map(self._mapper.map, result))

    async def get_in_time_slot(self, time_slot_id: int):
        slot_statement = select(TimeSlot).where(TimeSlot.id == time_slot_id)
        statement = select(Speech).where(Speech.time_slot_id == time_slot_id)
        async with self._factory() as session:
            slot_result = await session.scalars(slot_statement)
            result = await session.scalars(statement)
            slot = self._slot_mapper.map(slot_result.one())
            return slot, [self._mapper.map(it, fields_mapping={'time_slot': slot}) for it in result]

    async def get_all_slots(self):
        statement = select(TimeSlot)
        async with self._factory() as session:
            result = await session.execute(statement)
            return list(map(self._slot_mapper.map, result.scalars()))

    async def get_all_slot_ids(self):
        statement = select(TimeSlot.id)
        async with self._factory() as session:
            result = await session.execute(statement)
            return list(result.scalars().all())

    async def get_slot_ids_on_day(self, date: datetime.date):
        statement = select(TimeSlot.id).where(TimeSlot.date == date)
        async with self._factory() as session:
            result = await session.execute(statement)
            return list(result.scalars().all())

    async def get_all_dates(self):
        statement = select(TimeSlot.date).distinct()
        async with self._factory() as session:
            result = await session.execute(statement)
            return list(result.scalars().all())

    async def save_selection(self, user_id: int, slot_id: int, speech_id: int | None):
        delete_statement = delete(Selection).where(
            (Selection.attendee == user_id) & (Selection.time_slot_id == slot_id))
        async with self._factory() as session, session.begin():
            await session.execute(delete_statement)
            if speech_id is not None:
                selection = Selection(
                    attendee=user_id, time_slot_id=slot_id, speech_id=speech_id)
                session.add(selection)
