import datetime
import logging
from collections.abc import Collection, Iterable
from typing import Any
from zoneinfo import ZoneInfo

import automapper  # type: ignore
from sqlalchemy import delete, insert, select, tuple_, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.orm import aliased, contains_eager, selectinload

from dto import SelectionDto, SpeechDto, TimeSlotDto

from .tables import Selection, Settings, Speech, TimeSlot


class SpeechRepository:
    def __init__(self, factory: async_sessionmaker[AsyncSession],
                 timezone: datetime.tzinfo | None = None) -> None:
        self._factory = factory
        self._timezone = timezone or ZoneInfo('Asia/Novosibirsk')
        self._mapper = automapper.mapper.to(SpeechDto)
        self._to_speech_mapper = automapper.mapper.to(Speech)
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
            speeches = result.all()
            _update_speeches_slot_timezone(speeches, self._timezone)
            return [self._mapper.map(speech) for speech in speeches]

    async def get_in_time_slot(self, time_slot_id: int):
        slot_statement = select(TimeSlot).where(TimeSlot.id == time_slot_id)
        statement = select(Speech).where(Speech.time_slot_id == time_slot_id)
        async with self._factory() as session:
            slot_result = await session.scalars(slot_statement)
            result = await session.scalars(statement)
            slot = self._map_slot_to_dto(slot_result.one())
            return slot, [self._mapper.map(it, fields_mapping={'time_slot': slot}) for it in result]

    async def get_all_slots(self):
        statement = select(TimeSlot).order_by(TimeSlot.date, TimeSlot.start_time)
        async with self._factory() as session:
            result = await session.scalars(statement)
            return list(map(self._map_slot_to_dto, result))

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
        statement = select(TimeSlot.date).distinct().order_by(TimeSlot.date)
        async with self._factory() as session:
            result = await session.scalars(statement)
            return result.all()

    async def find_or_create_slots(self, slots: Collection[TimeSlotDto], session: AsyncSession):
        slot_descriptors = [(slot.date, self._shift_time(slot.start_time), self._shift_time(slot.end_time))
                            for slot in slots]
        statement = (select(TimeSlot)
                     .where(tuple_(TimeSlot.date, TimeSlot.start_time, TimeSlot.end_time).in_(slot_descriptors)))
        result = await session.scalars(statement)
        mapping = {self._time_tuple(slot): self._map_slot_to_dto(slot) for slot in result}
        not_found = (slot for slot in slots if (slot.date, slot.start_time, slot.end_time) not in mapping)
        entities = [self._map_slot_from_dto(slot) for slot in not_found]
        if entities:
            self._logger.info('Creating new %d time slots', len(entities))
            session.add_all(entities)
            await session.flush()
            for slot in entities:
                mapping[self._time_tuple(slot)] = self._map_slot_to_dto(slot)
        return mapping

    async def update_or_insert_speeches(self, speeches: Collection[SpeechDto], session: AsyncSession):
        self._logger.info('Updating %d speeches', len(speeches))
        speech_descriptors = [(speech.time_slot.id, speech.location) for speech in speeches]
        statement = select(Speech).where(tuple_(Speech.time_slot_id, Speech.location).in_(speech_descriptors))
        result = await session.scalars(statement)
        existing = {(speech.time_slot_id, speech.location): speech for speech in result}
        for speech in speeches:
            slot = speech.time_slot.id
            assert slot is not None
            if (slot, speech.location) in existing:
                entity = existing[slot, speech.location]
                _update_speech(entity, speech)
            else:
                entity = self._to_speech_mapper.map(
                    speech,
                    fields_mapping={
                        'time_slot': None,
                        'time_slot_id': speech.time_slot.id},
                    skip_none_values=True)
            session.add(entity)

    def delete_speeches(self, speeches: Iterable[tuple[int, str]], session: AsyncSession):
        self._logger.info('Deleting some speeches')
        statement = (delete(Speech)
                     .where(tuple_(Speech.time_slot_id, Speech.location).in_(speeches)))
        return session.execute(statement)

    def _map_slot_to_dto(self, slot: TimeSlot):
        return TimeSlotDto(id=slot.id, date=slot.date,
                           start_time=slot.start_time.replace(tzinfo=self._timezone),
                           end_time=slot.end_time.replace(tzinfo=self._timezone))

    def _map_slot_from_dto(self, slot: TimeSlotDto):
        assert slot.id is None
        return TimeSlot(date=slot.date,
                        start_time=self._shift_time(slot.start_time),
                        end_time=self._shift_time(slot.end_time))

    def _shift_time(self, time: datetime.time):
        assert time.tzinfo == self._timezone
        return time.replace(tzinfo=None)

    def _time_tuple(self, slot: TimeSlot):
        return slot.date, slot.start_time.replace(tzinfo=self._timezone), slot.end_time.replace(tzinfo=self._timezone)


class UserRepository:
    def __init__(self, factory: async_sessionmaker[AsyncSession]):
        self._factory = factory
        self._logger = logging.getLogger(__name__)

    async def get_notification_setting(self, user_id: int):
        statement = select(Settings.notifications_enabled).where(Settings.user_id == user_id)
        async with self._factory() as session:
            return await session.scalar(statement)

    def register_user(self, user_id: int, username: str):
        return self._insert_or_update_setting(user_id, 'username', username)

    def save_notification_setting(self, user_id: int, enabled: bool):
        return self._insert_or_update_setting(user_id, 'notifications_enabled', enabled)

    def set_admin(self, user_id: int, admin: bool):
        return self._insert_or_update_setting(user_id, 'admin', admin)

    async def is_admin(self, user_id: int):
        statement = select(Settings.admin).where(Settings.user_id == user_id)
        async with self._factory() as session:
            result = await session.scalar(statement)
            return bool(result)

    async def set_admin_by_username(self, username: str, admin: bool):
        self._logger.info('Setting admin status for user %s to %s', username, admin)
        update_query = update(Settings).where(Settings.username == username).values(admin=admin)
        async with self._factory() as session, session.begin():
            updated = await session.execute(update_query)
            return updated.rowcount > 0

    async def _insert_or_update_setting(self, user_id: int, column: str, value: Any):
        self._logger.info('Saving setting for user %d, column %s, value %s', user_id, column, value)
        update_query = update(Settings).where(Settings.user_id == user_id).values({column: value})
        insert_query = insert(Settings).values({'user_id': user_id, column: value})
        async with self._factory() as session, session.begin():
            updated = await session.execute(update_query)
            if not updated.rowcount:
                await session.execute(insert_query)


class SelectionRepository:
    def __init__(self, factory: async_sessionmaker[AsyncSession], timezone: datetime.tzinfo | None = None):
        self._factory = factory
        self._timezone = timezone or ZoneInfo('Asia/Novosibirsk')
        self._selection_mapper = automapper.mapper.to(SelectionDto)
        self._speech_mapper = automapper.mapper.to(SpeechDto)
        self._logger = logging.getLogger(__name__)

    async def get_selected_speeches(self, user_id: int, date: datetime.date | None = None):
        statement = (select(Speech)
                     .join(Selection).where(Selection.attendee == user_id)
                     .join(TimeSlot).order_by(TimeSlot.date, TimeSlot.start_time)
                     .options(contains_eager(Speech.time_slot)))
        if date is not None:
            statement = statement.where(TimeSlot.date == date)
        async with self._factory() as session:
            result = await session.scalars(statement)
            speeches = result.all()
            _update_speeches_slot_timezone(speeches, self._timezone)
            return [self._speech_mapper.map(speech) for speech in speeches]

    async def save_selection(self, user_id: int, slot_id: int, speech_id: int | None):
        self._logger.info(
            'Saving selection for user %d, slot %d, speech %s', user_id, slot_id, speech_id)
        delete_statement = delete(Selection).where(
            (Selection.attendee == user_id) & (Selection.time_slot_id == slot_id))
        async with self._factory() as session, session.begin():
            await session.execute(delete_statement)
            if speech_id is not None:
                selection = Selection(
                    attendee=user_id, time_slot_id=slot_id, speech_id=speech_id)
                session.add(selection)

    async def get_users_that_selected(self, slot_id: int):
        query = (select(Selection).where(Selection.time_slot_id == slot_id)
                 .outerjoin(Settings, Selection.attendee == Settings.user_id)
                 .where(Settings.notifications_enabled.is_distinct_from(False))
                 .options(selectinload(Selection.speech)))
        dummy_slot = TimeSlotDto(0, datetime.date(1, 1, 1), datetime.time(), datetime.time())
        async with self._factory() as session:
            result = await session.scalars(query)
            return [self._selection_mapper.map(row, fields_mapping={'speech.time_slot': dummy_slot}) for row in result]

    async def get_changing_users(self, current_slot_id: int, previous_slot_id: int):
        previous_speech = aliased(Speech)
        previous_selection = aliased(Selection)
        query = (select(Selection)
                 .where(Selection.time_slot_id == current_slot_id)
                 .outerjoin(Settings, Selection.attendee == Settings.user_id)
                 .where(Settings.notifications_enabled.is_distinct_from(False))
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

    async def get_user_ids_that_selected(self, slot_ids: Iterable[int]):
        query = (select(Selection.attendee, Selection.time_slot_id).where(Selection.time_slot_id.in_(slot_ids))
                 .order_by(Selection.attendee))
        async with self._factory() as session:
            result = await session.execute(query)
            return result.tuples().all()


def _update_speeches_slot_timezone(speeches: Iterable[Speech], timezone: datetime.tzinfo):
    for speech in speeches:
        slot = speech.time_slot
        if slot.start_time.tzinfo is None:
            slot.start_time = slot.start_time.replace(tzinfo=timezone)
        if slot.end_time.tzinfo is None:
            slot.end_time = slot.end_time.replace(tzinfo=timezone)


def _update_speech(speech: Speech, dto: SpeechDto):
    time_slot = dto.time_slot.id
    assert time_slot is not None
    if speech.time_slot_id != time_slot:
        speech.time_slot_id = time_slot
    if speech.title != dto.title:
        speech.title = dto.title
    if speech.speaker != dto.speaker:
        speech.speaker = dto.speaker
    if speech.location != dto.location:
        speech.location = dto.location
