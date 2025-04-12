from unittest.mock import AsyncMock

import pytest
import pytest_asyncio
from aiogram.types import Chat, InaccessibleMessage
from freezegun import freeze_time
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import data.mock_data
import data.setup
from data.repository import Repository
from handlers import general


@pytest_asyncio.fixture  # type: ignore
async def repository():
    engine = create_async_engine('sqlite+aiosqlite:///:memory:')
    session_maker = async_sessionmaker(engine)
    await data.setup.create_tables(engine)
    await data.mock_data.fill_tables(session_maker)
    return Repository(session_maker)


@pytest.mark.asyncio
async def test_start():
    message = AsyncMock(text='/start')
    state_mock = AsyncMock()
    await general.handle_start(message, state_mock)
    message.answer.assert_called_once()
    args = message.answer.await_args.args
    assert '/configure' in args[0]
    assert '/schedule' in args[0]
    assert '/personal' in args[0]


@pytest.mark.asyncio
async def test_handle_personal_view(repository: Repository):
    message = AsyncMock()
    await general.handle_schedule(message)
    message.answer.assert_called_once()
    args = message.answer.await_args.args
    assert 'Какую часть расписания' in args[0]


@pytest.mark.asyncio
async def test_schedule_all(repository: Repository):
    callback = AsyncMock(data='show_general_all')

    await general.handle_schedule_selection(callback, repository)
    callback.answer.assert_called_once()
    callback.message.answer.assert_called_once()
    args = callback.message.answer.await_args.args
    for substring in ('About something', 'About something else', 'Alternative point', 'New day talk',
                      'Alternative day 2', 'Dr. John Doe', 'Jane Doe', 'Mr. Alternative', 'New speaker', 'A', 'B',
                      '01.06', '02.06', '9:00', '10:00', '11:00'):
        assert substring in args[0]


@pytest.mark.asyncio
@freeze_time('2025-06-01')
async def test_schedule_today(repository: Repository):
    callback = AsyncMock(data='show_general_today')

    await general.handle_schedule_selection(callback, repository)
    callback.answer.assert_called_once()
    callback.message.answer.assert_called_once()
    args = callback.message.answer.await_args.args
    for substring in ('About something', 'About something else', 'Alternative point', 'Dr. John Doe', 'Jane Doe',
                      'Mr. Alternative', 'A', 'B', '01.06', '9:00', '10:00', '11:00'):
        assert substring in args[0]
    for substring in 'New day talk', 'Alternative day 2', 'New speaker', '02.06':
        assert substring not in args[0]


@pytest.mark.asyncio
@freeze_time('2025-06-01')
async def test_schedule_tomorrow(repository: Repository):
    callback = AsyncMock(data='show_general_tomorrow')

    await general.handle_schedule_selection(callback, repository)
    callback.answer.assert_called_once()
    callback.message.answer.assert_called_once()
    args = callback.message.answer.await_args.args
    for substring in ('New day talk', 'Alternative day 2', 'Mr. Alternative', 'New speaker', 'A', 'B', '02.06', '9:00',
                      '10:00'):
        assert substring in args[0]
    for substring in ('About something', 'About something else', 'Alternative point', 'Dr. John Doe', 'Jane Doe',
                      '01.06', '11:00'):
        assert substring not in args[0]


@pytest.mark.asyncio
async def test_handle_personal_view_inaccessible(repository: Repository):
    callback = AsyncMock(data='show_personal_all')
    callback.message = InaccessibleMessage(
        chat=Chat(id=1, type=''), message_id=21)
    await general.handle_schedule_selection(callback, repository)
    callback.answer.assert_called_once()
    args = callback.answer.await_args.args
    assert 'устарело' in args[0]


@pytest.mark.asyncio
async def test_handle_personal_view_wrong(repository: Repository, caplog: pytest.LogCaptureFixture):
    callback = AsyncMock(data='asdf')
    await general.handle_schedule_selection(callback, repository)
    assert 'Received unknown general command asdf' in caplog.text
    callback.answer.assert_awaited_once_with('Что-то пошло не так')
