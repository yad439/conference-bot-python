from unittest.mock import AsyncMock

import pytest
import pytest_asyncio
from aiogram.types import Chat, InaccessibleMessage
from freezegun import freeze_time
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import data.mock_data
import data.setup
from data.repository import Repository
from data.tables import Selection
from handlers.personal_view import handle_personal_view, handle_personal_view_selection


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
    message = AsyncMock()
    await handle_personal_view(message)
    message.answer.assert_called_once()
    args = message.answer.await_args.args
    assert 'Какую часть расписания' in args[0]


@pytest.mark.asyncio
async def test_handle_personal_view_all(repository: Repository):
    callback = AsyncMock(data='show_personal_all')
    callback.from_user.id = 42
    await handle_personal_view_selection(callback, repository)
    callback.answer.assert_called_once()
    callback.message.answer.assert_called_once()
    args = callback.message.answer.await_args.args
    for substring in ('About something', 'About something else',
                      'Alternative day 2', 'Dr. John Doe', 'Jane Doe', 'Mr. Alternative', 'A', 'B',
                      '01.06', '02.06', '9:00', '10:00', '11:00'):
        assert substring in args[0]
    for substring in 'Alternative point', 'New day talk':
        assert substring not in args[0]


@pytest.mark.asyncio
@freeze_time('2025-05-01')
@pytest.mark.parametrize('query,user', [('show_personal_all', 41),
                         ('show_personal_today', 42), ('show_personal_tomorrow', 42)])
async def test_handle_personal_view_empty(repository: Repository, query: str, user: int):
    callback = AsyncMock(data=query)
    callback.from_user.id = user
    await handle_personal_view_selection(callback, repository)
    callback.answer.assert_called_once()
    callback.message.answer.assert_called_once()
    args = callback.message.answer.await_args.args
    assert 'не выбрали' in args[0]


@pytest.mark.asyncio
@freeze_time('2025-06-01')
async def test_handle_personal_view_today(repository: Repository):
    callback = AsyncMock(data='show_personal_today')
    callback.from_user.id = 42
    await handle_personal_view_selection(callback, repository)
    callback.answer.assert_called_once()
    callback.message.answer.assert_called_once()
    args = callback.message.answer.await_args.args
    for substring in ('About something', 'About something else',
                      'Dr. John Doe', 'Jane Doe', 'A',
                      '01.06', '9:00', '10:00', '11:00'):
        assert substring in args[0]
    for substring in 'Alternative point', 'Alternative day 2', 'New day talk', 'Mr. Alternative', 'B', '02.06':
        assert substring not in args[0]


@pytest.mark.asyncio
@freeze_time('2025-06-01')
async def test_handle_personal_view_tomorrow(repository: Repository):
    callback = AsyncMock(data='show_personal_tomorrow')
    callback.from_user.id = 42
    await handle_personal_view_selection(callback, repository)
    callback.answer.assert_called_once()
    callback.message.answer.assert_called_once()
    args = callback.message.answer.await_args.args
    for substring in 'Alternative day 2', 'Mr. Alternative', 'B', '02.06', '9:00', '10:00':
        assert substring in args[0]
    for substring in ('About something', 'About something else', 'Alternative point', 'New day talk', 'Dr. John Doe',
                      'Jane Doe', 'A:', '01.06', '11:00'):
        assert substring not in args[0]


@pytest.mark.asyncio
async def test_handle_personal_view_inaccessible(repository: Repository):
    callback = AsyncMock(data='show_personal_all')
    callback.from_user.id = 42
    callback.message = InaccessibleMessage(
        chat=Chat(id=1, type=''), message_id=21)
    await handle_personal_view_selection(callback, repository)
    callback.answer.assert_called_once()
    args = callback.answer.await_args.args
    assert 'устарело' in args[0]


@pytest.mark.asyncio
async def test_handle_personal_view_wrong(repository: Repository, caplog: pytest.LogCaptureFixture):
    callback = AsyncMock(data='asdf')
    callback.from_user.id = 42
    await handle_personal_view_selection(callback, repository)
    assert 'Received unknown personal command asdf' in caplog.text
    callback.answer.assert_awaited_once_with('Что-то пошло не так')
