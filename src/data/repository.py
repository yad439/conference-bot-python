import datetime
import logging

import automapper  # type: ignore
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.orm import aliased, contains_eager, selectinload

from dto import SelectionDto, SpeechDto, TimeSlotDto

from .tables import Selection, Speech, TimeSlot


class Repository:
    def __init__(self, factory: async_sessionmaker[AsyncSession]) -> None:
        self._factory = factory
        self._mapper = automapper.mapper.to(SpeechDto)
        self._slot_mapper = automapper.mapper.to(TimeSlotDto)
        self._selection_mapper = automapper.mapper.to(SelectionDto)
        self._logger = logging.getLogger(__name__)

    def get_session(self):
        return self._factory()

    async def get_all_speeches(self, date: datetime.date | None = None):
        statement = (select(Speech).join(Speech.time_slot)
                     .order_by(TimeSlot.date, Speech.location, TimeSlot.start_time)
                     .options(contains_eager(Speech.time_slot)))
        if date is not None:
            statement = statement.where(TimeSlot.date == date)
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

    async def get_selected_speeches(self, user_id: int, date: datetime.date | None = None):
        statement = (select(Speech)
                     .join(Selection).where(Selection.attendee == user_id)
                     .join(TimeSlot).order_by(TimeSlot.date, TimeSlot.start_time)
                     .options(contains_eager(Speech.time_slot)))
        if date is not None:
            statement = statement.where(TimeSlot.date == date)
        async with self._factory() as session:
            result = await session.scalars(statement)
            return list(map(self._mapper.map, result))

    async def get_all_slots(self):
        statement = select(TimeSlot).order_by(TimeSlot.date, TimeSlot.start_time)
        async with self._factory() as session:
            result = await session.scalars(statement)
            return list(map(self._slot_mapper.map, result))

    async def get_all_slot_ids(self):
        statement = select(TimeSlot.id)
        async with self._factory() as session:
            result = await session.scalars(statement)
            return result.all()

    async def get_slot_ids_on_day(self, date: datetime.date):
        statement = select(TimeSlot.id).where(TimeSlot.date == date)
        async with self._factory() as session:
            result = await session.scalars(statement)
            return result.all()

    async def get_all_dates(self):
        statement = select(TimeSlot.date).distinct()
        async with self._factory() as session:
            result = await session.scalars(statement)
            return result.all()

    async def save_selection(self, user_id: int, slot_id: int, speech_id: int | None):
        self._logger.info(
            'Saving selection for user %d, slot %d, speech %d', user_id, slot_id, speech_id)
        delete_statement = delete(Selection).where(
            (Selection.attendee == user_id) & (Selection.time_slot_id == slot_id))
        async with self._factory() as session, session.begin():
            await session.execute(delete_statement)
            if speech_id is not None:
                selection = Selection(
                    attendee=user_id, time_slot_id=slot_id, speech_id=speech_id)
                session.add(selection)

    async def get_users_that_selected(self, slot_id: int):
        query = select(Selection).where(Selection.time_slot_id == slot_id).options(selectinload(Selection.speech))
        dummy_slot = TimeSlotDto(0, datetime.date(1, 1, 1), datetime.time(), datetime.time())
        async with self._factory() as session:
            result = await session.scalars(query)
            return [self._selection_mapper.map(row, fields_mapping={'speech.time_slot': dummy_slot}) for row in result]

    async def get_changing_users(self, current_slot_id: int, previous_slot_id: int):
        previous_speech = aliased(Speech)
        previous_selection = aliased(Selection)
        query = (select(Selection)
                 .where(Selection.time_slot_id == current_slot_id)
                 .outerjoin(previous_selection,
                            (Selection.attendee == previous_selection.attendee)
                            & (previous_selection.time_slot_id == previous_slot_id))
                 .join(Speech, Selection.speech)
                 .outerjoin(previous_speech, previous_selection.speech)
                 .where(Speech.location.is_distinct_from(previous_speech.location))
                 .options(contains_eager(Selection.speech)))
        dummy_slot = TimeSlotDto(0, datetime.date(1, 1, 1), datetime.time(), datetime.time())
        async with self._factory() as session:
            result = await session.scalars(query)
            return [self._selection_mapper.map(row, fields_mapping={'speech.time_slot': dummy_slot}) for row in result]
