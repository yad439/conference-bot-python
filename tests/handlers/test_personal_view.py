import pytest
from unittest.mock import AsyncMock
import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import data.mock_data
import data.setup
from data.repository import Repository
from data.tables import Selection
from handlers.personal_view import handle_personal_view


@pytest_asyncio.fixture  # type: ignore
async def repository():
    engine = create_async_engine('sqlite+aiosqlite:///:memory:')
    session_maker = async_sessionmaker(engine)
    await data.setup.create_tables(engine)
    await data.mock_data.fill_tables(session_maker)
    async with session_maker() as session, session.begin():
        session.add_all((Selection(attendee=42, time_slot_id=1, speech_id=1),
                         Selection(attendee=42, time_slot_id=2, speech_id=2),
                         Selection(attendee=42, time_slot_id=3, speech_id=5)))
    return Repository(session_maker)


@pytest.mark.asyncio
async def test_handle_personal_view(repository: Repository):
    message = AsyncMock(text='/personal')
    message.from_user.id = 42
    await handle_personal_view(message, repository)
    message.answer.assert_called_once()
    args = message.answer.await_args.args
    for substring in ('About something', 'About something else',
                      'Alternative day 2', 'Dr. John Doe', 'Jane Doe', 'Mr. Alternative', 'A', 'B',
                      '01.06', '02.06', '9:00', '10:00', '11:00'):
        assert substring in args[0]
    for substring in 'Alternative point', 'New day talk':
        assert substring not in args[0]


@pytest.mark.asyncio
async def test_handle_personal_view_empty(repository: Repository):
    message = AsyncMock(text='/personal')
    message.from_user.id = 41
    await handle_personal_view(message, repository)
    message.answer.assert_called_once()
    args = message.answer.await_args.args
    assert 'не выбрали' in args[0]
