from unittest.mock import AsyncMock

import pytest
import pytest_asyncio
from aiogram.types import Chat, InaccessibleMessage
from freezegun import freeze_time
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

import data.mock_data
import data.setup
from data.repository import SelectionRepository, SpeechRepository
from data.tables import Selection
from handlers.personal_view import get_router, handle_personal_view, handle_personal_view_selection


@pytest_asyncio.fixture  # type: ignore
async def session_maker():
    engine = create_async_engine('sqlite+aiosqlite:///:memory:')
    session_maker = async_sessionmaker(engine)
    await data.setup.create_tables(engine)
    await data.mock_data.fill_tables(session_maker)
    async with session_maker() as session, session.begin():
        session.add_all((Selection(attendee=42, time_slot_id=1, speech_id=1),
                         Selection(attendee=42, time_slot_id=2, speech_id=2),
                         Selection(attendee=42, time_slot_id=3, speech_id=5)))
    return session_maker


@pytest_asyncio.fixture  # type: ignore
async def speech_repository(session_maker: async_sessionmaker[AsyncSession]):
    return SpeechRepository(session_maker)


@pytest_asyncio.fixture  # type: ignore
async def selection_repository(session_maker: async_sessionmaker[AsyncSession]):
    return SelectionRepository(session_maker)


def test_router():
    router = get_router()
    assert router is not None


@pytest.mark.asyncio
async def test_handle_personal_view(speech_repository: SpeechRepository):
    message = AsyncMock()
    await handle_personal_view(message, speech_repository)
    message.answer.assert_called_once()
    args = message.answer.await_args.args
    assert 'Какую часть расписания' in args[0]


@pytest.mark.asyncio
async def test_handle_personal_view_all(selection_repository: SelectionRepository):
    callback = AsyncMock(data='show_personal_all')
    callback.from_user.id = 42
    await handle_personal_view_selection(callback, selection_repository)
    callback.answer.assert_called_once()
    callback.message.answer.assert_called()
    text = '\n'.join(arg.kwargs['text'] for arg in callback.message.answer.await_args_list)
    for substring in ('About something', 'About something else',
                      'Alternative day 2', 'Dr. John Doe', 'Jane Doe', 'Mr. Alternative', 'A', 'B',
                      '01.06', '02.06', '9:00', '10:00', '11:00'):
        assert substring in text
    for substring in 'Alternative point', 'New day talk':
        assert substring not in text


@pytest.mark.asyncio
@freeze_time('2025-05-01')
@pytest.mark.parametrize(('query', 'user'), [('show_personal_all', 41), ('show_personal_today', 42),
                         ('show_personal_tomorrow', 42), ('show_personal_date#2025-05-01:+0700', 42)])
async def test_handle_personal_view_empty(selection_repository: SelectionRepository, query: str, user: int):
    callback = AsyncMock(data=query)
    callback.from_user.id = user
    await handle_personal_view_selection(callback, selection_repository)
    callback.answer.assert_called_once()
    callback.message.answer.assert_called_once()
    args = callback.message.answer.await_args.args
    assert 'не выбрали' in args[0]


@pytest.mark.asyncio
@freeze_time('2025-06-01')
@pytest.mark.parametrize('query', ['show_personal_today', 'show_personal_date#2025-06-01:+0700'])
async def test_handle_personal_view_today(selection_repository: SelectionRepository, query: str):
    callback = AsyncMock(data=query)
    callback.from_user.id = 42
    await handle_personal_view_selection(callback, selection_repository)
    callback.answer.assert_called_once()
    callback.message.answer.assert_called_once()
    args = callback.message.answer.await_args.kwargs['text']
    for substring in ('About something', 'About something else',
                      'Dr. John Doe', 'Jane Doe', 'A',
                      '01.06', '9:00', '10:00', '11:00'):
        assert substring in args
    for substring in 'Alternative point', 'Alternative day 2', 'New day talk', 'Mr. Alternative', 'B', '02.06':
        assert substring not in args


@pytest.mark.asyncio
@freeze_time('2025-06-01')
@pytest.mark.parametrize('query', ['show_personal_tomorrow', 'show_personal_date#2025-06-02:+0700'])
async def test_handle_personal_view_tomorrow(selection_repository: SelectionRepository, query: str):
    callback = AsyncMock(data=query)
    callback.from_user.id = 42
    await handle_personal_view_selection(callback, selection_repository)
    callback.answer.assert_called_once()
    callback.message.answer.assert_called_once()
    args = callback.message.answer.await_args.kwargs['text']
    for substring in 'Alternative day 2', 'Mr. Alternative', 'B', '02.06', '9:00', '10:00':
        assert substring in args
    for substring in ('About something', 'About something else', 'Alternative point', 'New day talk', 'Dr. John Doe',
                      'Jane Doe', 'A:', '01.06', '11:00'):
        assert substring not in args


@pytest.mark.asyncio
async def test_handle_personal_view_inaccessible(selection_repository: SelectionRepository):
    callback = AsyncMock(data='show_personal_all')
    callback.from_user.id = 42
    callback.message = InaccessibleMessage(
        chat=Chat(id=1, type=''), message_id=21)
    await handle_personal_view_selection(callback, selection_repository)
    callback.answer.assert_called_once()
    args = callback.answer.await_args.args
    assert 'устарело' in args[0]


@pytest.mark.asyncio
async def test_handle_personal_view_wrong(selection_repository: SelectionRepository, caplog: pytest.LogCaptureFixture):
    callback = AsyncMock(data='asdf')
    callback.from_user.id = 42
    await handle_personal_view_selection(callback, selection_repository)
    assert 'Received unknown personal command asdf' in caplog.text
    callback.answer.assert_awaited_once_with('Что-то пошло не так')
