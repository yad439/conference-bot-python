from collections import Counter

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

import data.mock_data
import data.setup
from data.repository import Repository
from data.tables import Selection, Settings


@pytest_asyncio.fixture  # type: ignore
async def session_maker():
    engine = create_async_engine('sqlite+aiosqlite:///:memory:')
    session_maker = async_sessionmaker(engine)
    await data.setup.create_tables(engine)
    await data.mock_data.fill_tables(session_maker)
    return session_maker


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

    assert Counter(map(lambda x: x.attendee, result)) == Counter((41, 42, 43, 45))
    assert tuple(map(lambda x: x.speech.id, result)) == (2, 2, 2, 2)


@pytest.mark.asyncio
async def test_get_changing_users(session_maker: async_sessionmaker[AsyncSession]):
    await _generate_mock_users(session_maker)
    repository = Repository(session_maker)

    result = await repository.get_changing_users(2, 1)

    assert Counter(map(lambda x: x.attendee, result)) == Counter((42, 43, 45))
    assert tuple(map(lambda x: x.speech.id, result)) == (2, 2, 2)


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
