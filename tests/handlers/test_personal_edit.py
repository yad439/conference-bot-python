# ruff : noqa: PLR0913,PLR0917,PLR2004

import datetime
from collections import Counter
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
import pytest_asyncio
from aiogram import Router
from aiogram.types import Chat, InaccessibleMessage, Message, User
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

import data.mock_data
import data.setup
from data.repository import SelectionRepository, SpeechRepository
from data.tables import Selection
from handlers import personal_edit
from handlers.personal_edit import EditingScene, EditIntentionScene, SelectDayScene, SelectSingleScene
from tests.fake_bot import StateFake


@pytest_asyncio.fixture  # type: ignore
async def session_maker():
    engine = create_async_engine('sqlite+aiosqlite:///:memory:')
    session_maker = async_sessionmaker(engine)
    await data.setup.create_tables(engine)
    await data.mock_data.fill_tables(session_maker)
    return session_maker


@pytest.fixture
def speech_repository(session_maker: async_sessionmaker[AsyncSession]) -> SpeechRepository:
    return SpeechRepository(session_maker)


@pytest.fixture
def selection_repository(session_maker: async_sessionmaker[AsyncSession]) -> SelectionRepository:
    return SelectionRepository(session_maker)


@pytest.fixture
def state():
    return StateFake()


@pytest.fixture
def user():
    return SimpleNamespace(id=42, first_name='Test', last_name='User', username='testuser')


@pytest.fixture
def message():
    return Message(message_id=1, date=datetime.datetime(2025, 1, 1),  # noqa: DTZ001
                   chat=Chat(id=1, type='private')).as_(AsyncMock())


def test_router():
    router = Router()
    personal_edit.init(router)
    assert router is not None


@pytest.mark.asyncio
async def test_editing_intent_all(speech_repository: SpeechRepository):
    wizard = AsyncMock()
    scene = EditIntentionScene(wizard)

    message = AsyncMock()
    await scene.on_enter(message)

    message = AsyncMock(text='Все')
    await scene.on_message(message, speech_repository)

    wizard.goto.assert_called_once()
    args = wizard.goto.await_args.args
    kwargs = wizard.goto.await_args.kwargs
    assert args[0] == personal_edit.EditingScene
    assert Counter(kwargs['slots']) == Counter(range(1, 4))


@pytest.mark.asyncio
async def test_editing_intent_day(speech_repository: SpeechRepository):
    wizard = AsyncMock()
    scene = EditIntentionScene(wizard)

    message = AsyncMock()
    await scene.on_enter(message)

    message = AsyncMock(text='День')
    await scene.on_message(message, speech_repository)

    wizard.goto.assert_called_once()
    args = wizard.goto.await_args.args
    assert args[0] == personal_edit.SelectDayScene


@pytest.mark.asyncio
async def test_editing_intent_single(speech_repository: SpeechRepository):
    wizard = AsyncMock()
    scene = EditIntentionScene(wizard)

    message = AsyncMock()
    await scene.on_enter(message)

    message = AsyncMock(text='Одну запись')
    await scene.on_message(message, speech_repository)

    wizard.goto.assert_called_once()
    args = wizard.goto.await_args.args
    assert args[0] == personal_edit.SelectSingleScene


@pytest.mark.asyncio
async def test_editing_intent_wrong(speech_repository: SpeechRepository):
    wizard = AsyncMock()
    scene = EditIntentionScene(wizard)

    message = AsyncMock()
    await scene.on_enter(message)

    message = AsyncMock(text='фжс')
    await scene.on_message(message, speech_repository)

    message.answer.assert_called_once()
    args = message.answer.await_args.args
    assert 'Выберете' in args[0]


TEST_DATA_DAYS = [
    ('1', [1, 2]),
    ('2', [3]),
    ('01.06', [1, 2]),
    ('02.06', [3]),
]


@pytest.mark.asyncio
@pytest.mark.parametrize(('day', 'slots'), TEST_DATA_DAYS)
async def test_select_day(speech_repository: SpeechRepository, state: StateFake, day: str, slots: list[int]):
    wizard = AsyncMock()
    scene = SelectDayScene(wizard)

    message = AsyncMock()
    await scene.on_enter(message, state, speech_repository)

    message.answer.assert_called_once()
    args = message.answer.await_args.args
    assert '01.06' in args[0]
    assert '02.06' in args[0]

    message = AsyncMock(text=day)
    await scene.on_message(message, state, speech_repository)

    wizard.goto.assert_called_once()
    args = wizard.goto.await_args.args
    kwargs = wizard.goto.await_args.kwargs
    assert args[0] == personal_edit.EditingScene
    assert kwargs['slots'] == slots


@pytest.mark.asyncio
@pytest.mark.parametrize('day', ['0', '-1', '3', 'fgz'])
async def test_select_day_wrong(speech_repository: SpeechRepository, state: StateFake, day: str):
    wizard = AsyncMock()
    scene = SelectDayScene(wizard)

    message = AsyncMock()
    await scene.on_enter(message, state, speech_repository)

    message.answer.assert_called_once()
    args = message.answer.await_args.args
    assert '01.06' in args[0]
    assert '02.06' in args[0]

    message = AsyncMock(text=day)
    await scene.on_message(message, state, speech_repository)

    message.answer.assert_called_once()
    args = message.answer.await_args.args
    assert 'Выберете' in args[0]


@pytest.mark.asyncio
async def test_select_single(speech_repository: SpeechRepository, state: StateFake):
    wizard = AsyncMock()
    scene = SelectSingleScene(wizard)

    message = AsyncMock()
    await scene.on_enter(message, state, speech_repository)

    message.answer.assert_called_once()
    args = message.answer.await_args.args
    for substring in ['01.06', '02.06', '09:00', '10:00', '11:00']:
        assert substring in args[0]

    message = AsyncMock(text='1')
    await scene.on_message(message, state)

    wizard.goto.assert_called_once()
    args = wizard.goto.await_args.args
    kwargs = wizard.goto.await_args.kwargs
    assert args[0] == personal_edit.EditingScene
    assert kwargs['slots'] == (2,)


@pytest.mark.asyncio
@pytest.mark.parametrize('option', ['-1', '10', 'fgz'])
async def test_select_single_wrong(speech_repository: SpeechRepository, state: StateFake, option: str):
    wizard = AsyncMock()
    scene = SelectSingleScene(wizard)

    message = AsyncMock()
    await scene.on_enter(message, state, speech_repository)

    message.answer.assert_called_once()
    args = message.answer.await_args.args
    for substring in ['01.06', '02.06', '09:00', '10:00', '11:00']:
        assert substring in args[0]

    message = AsyncMock(text=option)
    await scene.on_message(message, state)

    message.answer.assert_called_once()
    args = message.answer.await_args.args
    assert 'Выберете' in args[0]


async def _add_initial(session_maker: async_sessionmaker[AsyncSession]):
    async with session_maker() as session, session.begin():
        session.add(Selection(attendee=42, time_slot_id=1, speech_id=1))


async def _setup_edit(session_maker: async_sessionmaker[AsyncSession], speech_repository: SpeechRepository,
                      state: StateFake, user: User, message: Message, query_enter: bool, exist: bool):
    if exist:
        await _add_initial(session_maker)
    wizard = AsyncMock()
    scene = EditingScene(wizard)

    if query_enter:
        query = AsyncMock(from_user=user, message=message)
        await scene.on_query_enter(query, state, speech_repository, [1, 2])
    else:
        await scene.on_enter(message, state, speech_repository, [1, 2])

    message.bot.assert_awaited()  # type: ignore
    text = message.bot.await_args.args[0].text  # type: ignore
    for substring in ['A', 'B', 'About something', 'Alternative point']:
        assert substring in text

    return wizard, scene


async def _assert_selected(session_maker: async_sessionmaker[AsyncSession], slot: int, speech: int | None):
    async with session_maker() as session:
        result = await session.scalars(select(Selection))
        if speech is None:
            assert result.first() is None
        else:
            selection = result.one()
            assert selection.attendee == 42
            assert selection.time_slot_id == slot
            assert selection.speech_id == speech


@pytest.mark.asyncio
@pytest.mark.parametrize('query_reply', [False, True])
@pytest.mark.parametrize('query_enter', [False, True])
@pytest.mark.parametrize('exist', [False, True])
async def test_edit(session_maker: async_sessionmaker[AsyncSession], selection_repository: SelectionRepository,
                    speech_repository: SpeechRepository, state: StateFake, user: User, message: Message,
                    query_reply: bool, query_enter: bool, exist: bool):
    wizard, scene = await _setup_edit(session_maker, speech_repository, state, user, message, query_enter, exist)

    if query_reply:
        query = AsyncMock(from_user=user, data='select#1#3')
        await scene.on_query(query, state, selection_repository)
    else:
        message = AsyncMock(text='B', from_user=user)
        await scene.on_message(message, state, selection_repository)

    wizard.retake.assert_called_once()
    wizard.retake.assert_awaited_once()
    kwargs = wizard.retake.await_args.kwargs
    assert kwargs['slots'] == [2]
    await _assert_selected(session_maker, 1, 3)


@pytest.mark.asyncio
@pytest.mark.parametrize('query_reply', [False, True])
@pytest.mark.parametrize('query_enter', [False, True])
@pytest.mark.parametrize('exist', [False, True])
async def test_edit_remove(session_maker: async_sessionmaker[AsyncSession], selection_repository: SelectionRepository,
                           speech_repository: SpeechRepository, state: StateFake, user: User, message: Message,
                           query_reply: bool, query_enter: bool, exist: bool):
    wizard, scene = await _setup_edit(session_maker, speech_repository, state, user, message, query_enter, exist)

    if query_reply:
        query = AsyncMock(from_user=user, data='select#1#-1')
        await scene.on_query(query, state, selection_repository)
    else:
        message = AsyncMock(text='Ничего', from_user=user)
        await scene.on_message(message, state, selection_repository)

    wizard.retake.assert_called_once()
    wizard.retake.assert_awaited_once()
    kwargs = wizard.retake.await_args.kwargs
    assert kwargs['slots'] == [2]
    await _assert_selected(session_maker, 1, None)


@pytest.mark.asyncio
@pytest.mark.parametrize('query_enter', [False, True])
async def test_edit_other(session_maker: async_sessionmaker[AsyncSession], selection_repository: SelectionRepository,
                          speech_repository: SpeechRepository, state: StateFake, user: User, message: Message,
                          query_enter: bool):
    wizard, scene = await _setup_edit(session_maker, speech_repository, state, user, message, query_enter, False)

    query = AsyncMock(from_user=user, data='select#3#4')
    await scene.on_query(query, state, selection_repository)

    wizard.retake.assert_not_called()
    await _assert_selected(session_maker, 3, 4)


@pytest.mark.asyncio
@pytest.mark.parametrize('query_enter', [False, True])
@pytest.mark.parametrize('exist', [False, True])
async def test_edit_wrong_message(session_maker: async_sessionmaker[AsyncSession],
                                  selection_repository: SelectionRepository, speech_repository: SpeechRepository,
                                  state: StateFake, user: User, message: Message, query_enter: bool, exist: bool):
    _, scene = await _setup_edit(session_maker, speech_repository, state, user, message, query_enter, exist)

    message = AsyncMock(text='C', from_user=user)
    await scene.on_message(message, state, selection_repository)

    message.answer.assert_awaited_once()
    args = message.answer.await_args.args
    assert 'повторите' in args[0]


@pytest.mark.asyncio
@pytest.mark.skip(reason='Foreign key constraints are not enforced')
@pytest.mark.parametrize('query_enter', [False, True])
@pytest.mark.parametrize('exist', [False, True])
async def test_edit_wrong_query(session_maker: async_sessionmaker[AsyncSession],
                                selection_repository: SelectionRepository, speech_repository: SpeechRepository,
                                state: StateFake, user: User, message: Message, query_enter: bool, exist: bool):
    _, scene = await _setup_edit(session_maker, speech_repository, state, user, message, query_enter, exist)

    query = AsyncMock(from_user=user, data='select#1#10')
    await scene.on_query(query, state, selection_repository)

    query.answer.assert_awaited_once()
    args = query.answer.await_args.args
    assert 'не так' in args[0]


@pytest.mark.asyncio
async def test_edit_enter_inaccessible(caplog: pytest.LogCaptureFixture):
    wizard = AsyncMock()
    selection_repository = AsyncMock()
    state = AsyncMock()
    callback = AsyncMock(message=InaccessibleMessage(chat=Chat(id=1, type='private'), message_id=1))
    scene = EditingScene(wizard)

    await scene.on_query_enter(callback, state, selection_repository, [])

    callback.answer.assert_awaited_with('Что-то пошло не так')
    assert 'InaccessibleMessage' in caplog.text


@pytest.mark.asyncio
@pytest.mark.parametrize('query_enter', [False, True])
async def test_edit_end(selection_repository: SelectionRepository, state: StateFake, user: User, message: Message,
                        query_enter: bool):
    wizard = AsyncMock()
    scene = EditingScene(wizard)

    if query_enter:
        query = AsyncMock(message=message, from_user=user, data='select#1#3')
        await scene.on_query_enter(query, state, selection_repository, [])
    else:
        await scene.on_enter(message, state, selection_repository, [])

    message.bot.assert_awaited_once()  # type: ignore
    text = message.bot.await_args.args[0].text  # type: ignore
    assert 'Готово' in text
    wizard.exit.assert_called_once()


@pytest.mark.asyncio
@pytest.mark.parametrize('query_enter', [False, True])
async def test_edit_cancel(session_maker: async_sessionmaker[AsyncSession],
                           selection_repository: SelectionRepository, speech_repository: SpeechRepository,
                           state: StateFake, user: User, message: Message, query_enter: bool):
    wizard, scene = await _setup_edit(session_maker, speech_repository, state, user, message, query_enter, False)

    message = AsyncMock(text='Отмена', from_user=user)
    await scene.on_message(message, state, selection_repository)

    wizard.exit.assert_called_once()
    wizard.exit.assert_awaited_once()


@pytest.mark.asyncio
@pytest.mark.parametrize('exist', [False, True])
async def test_edit_off_scene(session_maker: async_sessionmaker[AsyncSession],
                              selection_repository: SelectionRepository, user: User, exist: bool):
    if exist:
        await _add_initial(session_maker)

    query = AsyncMock(from_user=user, data='select#1#3')
    await personal_edit.handle_selection_query(query, selection_repository)

    query.answer.assert_awaited_with('Сохранено')
    await _assert_selected(session_maker, 1, 3)


@pytest.mark.asyncio
@pytest.mark.parametrize('exist', [False, True])
async def test_edit_off_scene_remove(session_maker: async_sessionmaker[AsyncSession],
                                     selection_repository: SelectionRepository, user: User, exist: bool):
    if exist:
        await _add_initial(session_maker)

    query = AsyncMock(from_user=user, data='select#1#-1')
    await personal_edit.handle_selection_query(query, selection_repository)

    query.answer.assert_awaited_with('Сохранено')
    await _assert_selected(session_maker, 1, None)
