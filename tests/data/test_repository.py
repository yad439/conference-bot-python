import dataclasses
import datetime
from collections import Counter
from zoneinfo import ZoneInfo

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import selectinload

import data.mock_data
import data.setup
from data.repository import Repository
from data.tables import Selection, Settings, Speech, TimeSlot
from dto import SpeechDto, TimeSlotDto


@pytest_asyncio.fixture  # type: ignore
async def session_maker():
    engine = create_async_engine('sqlite+aiosqlite:///:memory:')
    session_maker = async_sessionmaker(engine)
    await data.setup.create_tables(engine)
    await data.mock_data.fill_tables(session_maker)
    return session_maker


@pytest.fixture
def old_slots():
    timezone = ZoneInfo('Asia/Novosibirsk')
    return [
        TimeSlotDto(None, datetime.date(2025, 6, 1), datetime.time(9, tzinfo=timezone),
                    datetime.time(10, tzinfo=timezone)),
        TimeSlotDto(None, datetime.date(2025, 6, 1), datetime.time(10, tzinfo=timezone),
                    datetime.time(11, tzinfo=timezone)),
        TimeSlotDto(None, datetime.date(2025, 6, 2), datetime.time(9, tzinfo=timezone),
                    datetime.time(10, tzinfo=timezone)),
    ]


@pytest.fixture
def new_slot():
    timezone = ZoneInfo('Asia/Novosibirsk')
    return TimeSlotDto(None, datetime.date(2025, 6, 2), datetime.time(10, tzinfo=timezone),
                       datetime.time(11, tzinfo=timezone))


@pytest.fixture
def old_speeches(old_slots: list[TimeSlotDto]):
    return [
        SpeechDto(None, 'About something', 'Dr. John Doe', old_slots[0], 'A'),
        SpeechDto(None, 'About something else', 'Jane Doe', old_slots[1], 'A'),
        SpeechDto(None, 'Alternative point', 'Mr. Alternative', old_slots[0], 'B'),
        SpeechDto(None, 'New day talk', 'New speaker', old_slots[2], 'A'),
        SpeechDto(None, 'Alternative day 2', 'Mr. Alternative', old_slots[2], 'B')
    ]


@pytest.mark.asyncio
async def test_save_selection_add(session_maker: async_sessionmaker[AsyncSession]):
    repository = Repository(session_maker)

    await repository.save_selection(42, 1, 3)

    async with session_maker() as session:
        result = await session.scalars(select(Selection))
        selection = result.one()
        assert selection.attendee == 42
        assert selection.time_slot_id == 1
        assert selection.speech_id == 3


@pytest.mark.asyncio
async def test_save_selection_replace(session_maker: async_sessionmaker[AsyncSession]):
    async with session_maker() as session, session.begin():
        session.add(Selection(attendee=42, time_slot_id=1, speech_id=1))
    repository = Repository(session_maker)

    await repository.save_selection(42, 1, 3)

    async with session_maker() as session:
        result = await session.scalars(select(Selection))
        selection = result.one()
        assert selection.attendee == 42
        assert selection.time_slot_id == 1
        assert selection.speech_id == 3


@pytest.mark.asyncio
async def test_save_selection_remove(session_maker: async_sessionmaker[AsyncSession]):
    async with session_maker() as session, session.begin():
        session.add(Selection(attendee=42, time_slot_id=1, speech_id=1))
    repository = Repository(session_maker)

    await repository.save_selection(42, 1, None)

    async with repository.get_session() as session:
        result = await session.scalars(select(Selection))
        assert result.first() is None


async def _generate_mock_users(session_maker: async_sessionmaker[AsyncSession]):
    async with session_maker() as session, session.begin():
        session.add_all((Selection(attendee=41, time_slot_id=1, speech_id=1),
                         Selection(attendee=41, time_slot_id=2, speech_id=2),
                         Selection(attendee=42, time_slot_id=1, speech_id=3),
                         Selection(attendee=42, time_slot_id=2, speech_id=2),
                         Selection(attendee=43, time_slot_id=2, speech_id=2),
                         Selection(attendee=44, time_slot_id=1, speech_id=1),
                         Selection(attendee=45, time_slot_id=2, speech_id=2),
                         Selection(attendee=46, time_slot_id=2, speech_id=2)))
        session.add_all((Settings(user_id=45, notifications_enabled=True),
                         Settings(user_id=46, notifications_enabled=False)))


@pytest.mark.asyncio
async def test_get_users_selected(session_maker: async_sessionmaker[AsyncSession]):
    await _generate_mock_users(session_maker)
    repository = Repository(session_maker)

    result = await repository.get_users_that_selected(2)

    assert Counter(x.attendee for x in result) == Counter((41, 42, 43, 45))
    assert tuple(x.speech.id for x in result) == (2, 2, 2, 2)


@pytest.mark.asyncio
async def test_get_changing_users(session_maker: async_sessionmaker[AsyncSession]):
    await _generate_mock_users(session_maker)
    repository = Repository(session_maker)

    result = await repository.get_changing_users(2, 1)

    assert Counter(x.attendee for x in result) == Counter((42, 43, 45))
    assert tuple(x.speech.id for x in result) == (2, 2, 2)


@pytest.mark.asyncio
@pytest.mark.parametrize('previous', [True, False, None])
async def test_save_notification_setting(session_maker: async_sessionmaker[AsyncSession], previous: bool | None):
    if previous is not None:
        async with session_maker() as session, session.begin():
            session.add(Settings(user_id=42, notifications_enabled=previous))
    repository = Repository(session_maker)

    await repository.save_notification_setting(42, True)

    async with session_maker() as session:
        result = await session.scalars(select(Settings))
        settings = result.one()
        assert settings.user_id == 42
        assert settings.notifications_enabled is True


@pytest.mark.asyncio
async def test_find_or_create_slots(session_maker: async_sessionmaker[AsyncSession], old_slots: list[TimeSlotDto],
                                    new_slot: TimeSlotDto):
    repository = Repository(session_maker)

    async with session_maker() as session, session.begin():
        slot_mapping = await repository.find_or_create_slots([*old_slots, new_slot], session)

    assert slot_mapping[old_slots[0].date, old_slots[0].start_time, old_slots[0].end_time] == 1
    assert slot_mapping[old_slots[1].date, old_slots[1].start_time, old_slots[1].end_time] == 2
    assert slot_mapping[old_slots[2].date, old_slots[2].start_time, old_slots[2].end_time] == 3
    assert slot_mapping[new_slot.date, new_slot.start_time, new_slot.end_time] == 4
    async with session_maker() as session:
        result = await session.scalar(select(TimeSlot).where(TimeSlot.id == 4))
        assert result is not None
        assert result.date == new_slot.date
        assert result.start_time == new_slot.start_time
        assert result.end_time == new_slot.end_time


@pytest.mark.asyncio
@pytest.mark.parametrize('location_new', [False, True])
async def test_insert_or_update_speeches(session_maker: async_sessionmaker[AsyncSession], old_speeches: list[SpeechDto],
                                         location_new: bool):
    repository = Repository(session_maker)
    updated_speech = dataclasses.replace(old_speeches[1], title='Updated Title', speaker='Updated Speaker')
    slot = dataclasses.replace(old_speeches[1].time_slot, id=2)
    updated_speech = dataclasses.replace(updated_speech, time_slot=slot)
    if location_new:
        updated_speech = dataclasses.replace(updated_speech, location='B')
        location = 'B'
    else:
        location = old_speeches[1].location

    async with session_maker() as session, session.begin():
        await repository.update_or_insert_speeches([updated_speech], session)

    async with session_maker() as session:
        result = await session.scalars(select(Speech).join(TimeSlot)
                                       .where((TimeSlot.date == slot.date)
                                              & (TimeSlot.start_time == slot.start_time)
                                              & (TimeSlot.end_time == slot.end_time)
                                              & (Speech.location == location))
                                       .options(selectinload(Speech.time_slot)))
        speech = result.one()
        assert speech.title == 'Updated Title'
        assert speech.speaker == 'Updated Speaker'
        assert speech.location == location
        assert speech.time_slot.date == slot.date
        assert speech.time_slot.start_time == slot.start_time
        assert speech.time_slot.end_time == slot.end_time


@pytest.mark.asyncio
async def test_delete_speeches(session_maker: async_sessionmaker[AsyncSession]):
    repository = Repository(session_maker)

    async with session_maker() as session, session.begin():
        await repository.delete_speeches([(1, 'B'), (2, 'A')], session)

    async with session_maker() as session:
        result = await session.scalars(select(Speech))
        speeches = result.all()
        assert len(speeches) == 3
        assert {speech.id for speech in speeches} == {1, 4, 5}
