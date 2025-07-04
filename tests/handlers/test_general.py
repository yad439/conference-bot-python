from pathlib import Path
from unittest.mock import AsyncMock

import pytest
import pytest_asyncio
from aiogram.types import Chat, FSInputFile, InaccessibleMessage
from freezegun import freeze_time
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import data.mock_data
import data.setup
from data.repository import SpeechRepository
from handlers import general
from utility import FileManager


@pytest_asyncio.fixture  # type: ignore
async def speech_repository():
    engine = create_async_engine('sqlite+aiosqlite:///:memory:')
    session_maker = async_sessionmaker(engine)
    await data.setup.create_tables(engine)
    await data.mock_data.fill_tables(session_maker)
    return SpeechRepository(session_maker)


@pytest.mark.asyncio
async def test_start():
    message = AsyncMock(text='/start')
    state_mock = AsyncMock()
    await general.handle_start(message, state_mock)
    message.answer.assert_awaited_once()
    args = message.answer.await_args.args
    assert '/configure' in args[0]
    assert '/schedule' in args[0]
    assert '/personal' in args[0]


@pytest.mark.asyncio
async def test_handle_personal_view(speech_repository: SpeechRepository):
    message = AsyncMock()
    await general.handle_schedule(message, speech_repository)
    message.answer.assert_awaited_once()
    args = message.answer.await_args.args
    assert 'Какую часть расписания' in args[0]


@pytest.mark.asyncio
async def test_schedule_all_first(speech_repository: SpeechRepository):
    callback = AsyncMock(data='show_general_all')
    file_manager = FileManager({'schedule': Path('schedule.txt')})

    await general.handle_schedule_selection(callback, speech_repository, file_manager)

    callback.answer.assert_awaited_once()
    callback.message.answer_document.assert_awaited_once()
    args = callback.message.answer_document.await_args.args
    assert isinstance(args[0], FSInputFile)
    assert args[0].path == Path('schedule.txt')


@pytest.mark.asyncio
async def test_schedule_all_repeat(speech_repository: SpeechRepository):
    callback = AsyncMock(data='show_general_all')
    file_manager = FileManager({'schedule': Path('schedule.txt')})
    file_manager.set_file_id('schedule', '1234567890')

    await general.handle_schedule_selection(callback, speech_repository, file_manager)

    callback.answer.assert_awaited_once()
    callback.message.answer_document.assert_awaited_once()
    args = callback.message.answer_document.await_args.args
    assert isinstance(args[0], str)
    assert args[0] == '1234567890'


@pytest.mark.asyncio
@freeze_time('2025-06-01')
@pytest.mark.parametrize('query', ['show_general_today', 'show_general_date#2025-06-01:+0700'])
async def test_schedule_today(speech_repository: SpeechRepository, query: str):
    callback = AsyncMock(data=query)
    file_manager = FileManager({})

    await general.handle_schedule_selection(callback, speech_repository, file_manager)

    callback.answer.assert_awaited_once()
    callback.message.answer.assert_awaited_once()
    args = callback.message.answer.await_args.args
    for substring in ('About something', 'About something else', 'Alternative point', 'Dr. John Doe', 'Jane Doe',
                      'Mr. Alternative', 'A', 'B', '01.06', '9:00', '10:00', '11:00'):
        assert substring in args[0]
    for substring in 'New day talk', 'Alternative day 2', 'New speaker', '02.06':
        assert substring not in args[0]


@pytest.mark.asyncio
@freeze_time('2025-06-01')
@pytest.mark.parametrize('query', ['show_general_tomorrow', 'show_general_date#2025-06-02:+0700'])
async def test_schedule_tomorrow(speech_repository: SpeechRepository, query: str):
    callback = AsyncMock(data=query)
    file_manager = FileManager({})

    await general.handle_schedule_selection(callback, speech_repository, file_manager)

    callback.answer.assert_awaited_once()
    callback.message.answer.assert_awaited_once()
    args = callback.message.answer.await_args.args
    for substring in ('New day talk', 'Alternative day 2', 'Mr. Alternative', 'New speaker', 'A', 'B', '02.06', '9:00',
                      '10:00'):
        assert substring in args[0]
    for substring in ('About something', 'About something else', 'Alternative point', 'Dr. John Doe', 'Jane Doe',
                      '01.06', '11:00'):
        assert substring not in args[0]


@pytest.mark.asyncio
@freeze_time('2025-05-01')
@pytest.mark.parametrize('query', ['show_general_today', 'show_general_tomorrow', 'show_general_date#2025-05-01:+0700'])
async def test_schedule_empty(speech_repository: SpeechRepository, query: str):
    callback = AsyncMock(data=query)
    file_manager = FileManager({})

    await general.handle_schedule_selection(callback, speech_repository, file_manager)

    callback.answer.assert_awaited_once()
    callback.message.answer.assert_awaited_once()
    args = callback.message.answer.await_args.args
    assert 'Ничего' in args[0]


@pytest.mark.asyncio
async def test_handle_personal_view_inaccessible(speech_repository: SpeechRepository):
    callback = AsyncMock(data='show_personal_all')
    callback.message = InaccessibleMessage(
        chat=Chat(id=1, type=''), message_id=21)
    file_manager = FileManager({})

    await general.handle_schedule_selection(callback, speech_repository, file_manager)

    callback.answer.assert_awaited_once()
    args = callback.answer.await_args.args
    assert 'устарело' in args[0]


@pytest.mark.asyncio
async def test_handle_personal_view_wrong(speech_repository: SpeechRepository, caplog: pytest.LogCaptureFixture):
    callback = AsyncMock(data='asdf')
    file_manager = FileManager({})
    await general.handle_schedule_selection(callback, speech_repository, file_manager)
    assert 'Received unknown general command asdf' in caplog.text
    callback.answer.assert_awaited_once_with('Что-то пошло не так')
