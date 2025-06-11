# ruff: noqa: PLR2004

import datetime
from unittest.mock import AsyncMock, call
from zoneinfo import ZoneInfo

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

import data.mock_data
import data.setup
from data.repository import SelectionRepository
from data.tables import Selection, Settings
from dto import TimeSlotDto
from notifications.changed import notify_schedule_change


@pytest_asyncio.fixture
async def session_maker():
    engine = create_async_engine('sqlite+aiosqlite:///:memory:')
    session_maker = async_sessionmaker(engine)
    await data.setup.create_tables(engine)
    await data.mock_data.fill_tables(session_maker)
    async with session_maker() as session, session.begin():
        session.add_all((Selection(attendee=41, time_slot_id=1, speech_id=1),
                         Selection(attendee=41, time_slot_id=2, speech_id=2),
                         Selection(attendee=42, time_slot_id=1, speech_id=3),
                         Selection(attendee=42, time_slot_id=2, speech_id=2),
                         Selection(attendee=43, time_slot_id=2, speech_id=2),
                         Selection(attendee=44, time_slot_id=1, speech_id=1),
                         Selection(attendee=45, time_slot_id=1, speech_id=3),
                         Selection(attendee=46, time_slot_id=1, speech_id=3),
                         Selection(attendee=45, time_slot_id=2, speech_id=2),
                         Selection(attendee=46, time_slot_id=2, speech_id=2)))
        session.add_all((Settings(user_id=45, notifications_enabled=True),
                         Settings(user_id=46, notifications_enabled=False)))
    return session_maker


@pytest.fixture
def selection_repository(session_maker: async_sessionmaker[AsyncSession]):
    return SelectionRepository(session_maker)


@pytest.mark.asyncio
async def test_notify_schedule_change(selection_repository: SelectionRepository):
    timezone = ZoneInfo('Asia/Novosibirsk')
    slots = [
        TimeSlotDto(1, datetime.date(2025, 6, 1), datetime.time(9, tzinfo=timezone),
                    datetime.time(10, tzinfo=timezone)),
        TimeSlotDto(2, datetime.date(2025, 6, 1), datetime.time(10, tzinfo=timezone),
                    datetime.time(11, tzinfo=timezone)),
        TimeSlotDto(3, datetime.date(2025, 6, 2), datetime.time(9, tzinfo=timezone),
                    datetime.time(10, tzinfo=timezone)),
    ]
    bot = AsyncMock()

    await notify_schedule_change(bot, selection_repository, slots)

    expected_calls = (
        call(41, 'Поменялось расписание для следующих слотов:\n09:00 - 10:00\n10:00 - 11:00\nПроверьте ваш выбор'),
        call(42, 'Поменялось расписание для следующих слотов:\n09:00 - 10:00\n10:00 - 11:00\nПроверьте ваш выбор'),
        call(43, 'Поменялось расписание для следующих слотов:\n10:00 - 11:00\nПроверьте ваш выбор'),
        call(44, 'Поменялось расписание для следующих слотов:\n09:00 - 10:00\nПроверьте ваш выбор'),
        call(45, 'Поменялось расписание для следующих слотов:\n09:00 - 10:00\n10:00 - 11:00\nПроверьте ваш выбор'),
        call(46, 'Поменялось расписание для следующих слотов:\n09:00 - 10:00\n10:00 - 11:00\nПроверьте ваш выбор'),
    )
    bot.send_message.assert_has_awaits(expected_calls, any_order=True)
    assert bot.send_message.await_count == 6
