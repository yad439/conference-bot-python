import asyncio
from unittest.mock import AsyncMock, call

import pytest
import pytest_asyncio
from apscheduler.schedulers.asyncio import AsyncIOScheduler  # type: ignore
from freezegun import freeze_time
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import data.mock_data
import data.setup
from data.repository import Repository
from data.tables import Selection
from notifications import event_start


@pytest_asyncio.fixture  # type: ignore
async def repository():
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
                         Selection(attendee=44, time_slot_id=1, speech_id=1)))
    return Repository(session_maker)


@pytest.mark.asyncio
async def test_notify_first(repository: Repository):
    bot = AsyncMock()

    await event_start.notify_first(bot, repository, 1, 5)

    args = (
        call(41, 'Через 5 минут начинается доклад "About something" (A)'),
        call(42, 'Через 5 минут начинается доклад "Alternative point" (B)'),
        call(44, 'Через 5 минут начинается доклад "About something" (A)'),
    )
    bot.send_message.assert_has_awaits(args, any_order=True)


@pytest.mark.asyncio
async def test_notify_change_location(repository: Repository):
    bot = AsyncMock()

    await event_start.notify_change_location(bot, repository, 2, 1, 5)

    args = (
        call(42, 'Через 5 минут начинается доклад "About something else" (A)'),
        call(43, 'Через 5 минут начинается доклад "About something else" (A)'),
    )
    bot.send_message.assert_has_awaits(args, any_order=True)


@pytest.mark.asyncio
async def test_configure(repository: Repository):
    bot = AsyncMock()
    scheduler = AsyncIOScheduler()
    semaphore = asyncio.Semaphore(0)

    async def release_semaphore(*_):
        semaphore.release()
    bot.send_message.side_effect = release_semaphore

    with freeze_time('2025-06-01 08:54:00', tick=True) as frozen_time:
        await event_start.configure_events(scheduler, repository, bot, 5)
        scheduler.start()

        bot.send_message.assert_not_called()

        frozen_time.tick(60)
        async with asyncio.timeout(5):
            for _ in range(3):
                await semaphore.acquire()

        args = (
            call(41, 'Через 5 минут начинается доклад "About something" (A)'),
            call(42, 'Через 5 минут начинается доклад "Alternative point" (B)'),
            call(44, 'Через 5 минут начинается доклад "About something" (A)'),
        )
        bot.send_message.assert_has_awaits(args, any_order=True)
        bot.send_message.reset_mock()

        frozen_time.move_to('2025-06-01 09:55:00')
        async with asyncio.timeout(5):
            for _ in range(2):
                await semaphore.acquire()

        args2 = (
            call(42, 'Через 5 минут начинается доклад "About something else" (A)'),
            call(43, 'Через 5 минут начинается доклад "About something else" (A)'),
        )
        bot.send_message.assert_has_awaits(args2, any_order=True)
