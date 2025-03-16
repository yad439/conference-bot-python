from collections import Counter
from typing import Any
import pytest
from unittest.mock import AsyncMock
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import data.mock_data
import data.setup
from data.repository import Repository
from data.tables import Selection

from handlers import personal_edit
from handlers.personal_edit import EditIntentionScene, EditingScene, SelectDayScene, SelectSingleScene


class StateFake:
    data: dict[str, Any] = {}

    async def update_data(self, **kwargs: Any):
        self.data.update(kwargs)

    async def get_data(self):
        return self.data

    async def get_value(self, key: str):
        return self.data[key]


@pytest_asyncio.fixture  # type: ignore
async def repository():
    engine = create_async_engine('sqlite+aiosqlite:///:memory:')
    session_maker = async_sessionmaker(engine)
    await data.setup.create_tables(engine)
    await data.mock_data.fill_tables(session_maker)
    return Repository(session_maker)


@pytest.fixture
def state():
    return StateFake()


@pytest.mark.asyncio
async def test_editing_intent_all(repository: Repository):
    wizard = AsyncMock()
    scene = EditIntentionScene(wizard)

    message = AsyncMock()
    await scene.on_enter(message)

    message = AsyncMock(text='Все')
    await scene.on_message(message, repository)

    wizard.goto.assert_called_once()
    args = wizard.goto.await_args.args
    kwargs = wizard.goto.await_args.kwargs
    assert args[0] == personal_edit.EditingScene
    assert Counter(kwargs['slots']) == Counter(range(1, 4))


@pytest.mark.asyncio
async def test_editing_intent_day(repository: Repository):
    wizard = AsyncMock()
    scene = EditIntentionScene(wizard)

    message = AsyncMock()
    await scene.on_enter(message)

    message = AsyncMock(text='День')
    await scene.on_message(message, repository)

    wizard.goto.assert_called_once()
    args = wizard.goto.await_args.args
    assert args[0] == personal_edit.SelectDayScene


@pytest.mark.asyncio
async def test_editing_intent_single(repository: Repository):
    wizard = AsyncMock()
    scene = EditIntentionScene(wizard)

    message = AsyncMock()
    await scene.on_enter(message)

    message = AsyncMock(text='Одну запись')
    await scene.on_message(message, repository)

    wizard.goto.assert_called_once()
    args = wizard.goto.await_args.args
    assert args[0] == personal_edit.SelectSingleScene


@pytest.mark.asyncio
async def test_editing_intent_wrong(repository: Repository):
    wizard = AsyncMock()
    scene = EditIntentionScene(wizard)

    message = AsyncMock()
    await scene.on_enter(message)

    message = AsyncMock(text='фжс')
    await scene.on_message(message, repository)

    message.answer.assert_called_once()
    args = message.answer.await_args.args
    assert 'Выберете' in args[0]

TEST_DATA_DAYS = [
    ('1', [1, 2]),
    ('2', [3])
]


@pytest.mark.asyncio
@pytest.mark.parametrize('day,slots', TEST_DATA_DAYS)
async def test_select_day(repository: Repository, state: StateFake, day: str, slots: list[int]):
    wizard = AsyncMock()
    scene = SelectDayScene(wizard)

    message = AsyncMock()
    await scene.on_enter(message, state, repository)

    message.answer.assert_called_once()
    args = message.answer.await_args.args
    assert '01.06' in args[0]
    assert '02.06' in args[0]

    message = AsyncMock(text=day)
    await scene.on_message(message, state, repository)

    wizard.goto.assert_called_once()
    args = wizard.goto.await_args.args
    kwargs = wizard.goto.await_args.kwargs
    assert args[0] == personal_edit.EditingScene
    assert kwargs['slots'] == slots


@pytest.mark.asyncio
@pytest.mark.parametrize('day', ['0', '-1', '3', 'fgz'])
async def test_select_day_wrong(repository: Repository, state: StateFake, day: str):
    wizard = AsyncMock()
    scene = SelectDayScene(wizard)

    message = AsyncMock()
    await scene.on_enter(message, state, repository)

    message.answer.assert_called_once()
    args = message.answer.await_args.args
    assert '01.06' in args[0]
    assert '02.06' in args[0]

    message = AsyncMock(text=day)
    await scene.on_message(message, state, repository)

    message.answer.assert_called_once()
    args = message.answer.await_args.args
    assert 'Выберете' in args[0]


@pytest.mark.asyncio
async def test_select_single(repository: Repository, state: StateFake):
    wizard = AsyncMock()
    scene = SelectSingleScene(wizard)

    message = AsyncMock()
    await scene.on_enter(message, state, repository)

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
    assert kwargs['slots'] == [2]


@pytest.mark.asyncio
@pytest.mark.parametrize('option', ['-1', '10', 'fgz'])
async def test_select_single_wrong(repository: Repository, state: StateFake, option: str):
    wizard = AsyncMock()
    scene = SelectSingleScene(wizard)

    message = AsyncMock()
    await scene.on_enter(message, state, repository)

    message.answer.assert_called_once()
    args = message.answer.await_args.args
    for substring in ['01.06', '02.06', '09:00', '10:00', '11:00']:
        assert substring in args[0]

    message = AsyncMock(text=option)
    await scene.on_message(message, state)

    message.answer.assert_called_once()
    args = message.answer.await_args.args
    assert 'Выберете' in args[0]


@pytest.mark.asyncio
async def test_edit_add(repository: Repository, state: StateFake):
    wizard = AsyncMock()
    scene = EditingScene(wizard)

    message = AsyncMock()
    await scene.on_enter(message, state, repository, [1, 2])

    message.answer.assert_called_once()
    args = message.answer.await_args.args
    for substring in ['A', 'B', 'About something', 'Alternative point']:
        assert substring in args[0]

    message = AsyncMock(text='B')
    message.from_user.id = 42
    await scene.on_message(message, state, repository)

    wizard.retake.assert_called_once()
    kwargs = wizard.retake.await_args.kwargs
    assert kwargs['slots'] == [2]
    async with repository.get_session() as session:
        result = await session.scalars(select(Selection))
        selection = result.one()
        assert selection.attendee == 42
        assert selection.time_slot_id == 1
        assert selection.speech_id == 3


@pytest.mark.asyncio
async def test_edit_replace(repository: Repository, state: StateFake):
    async with repository.get_session() as session:
        session.add(Selection(attendee=42, time_slot_id=1, speech_id=1))
        await session.commit()
    wizard = AsyncMock()
    scene = EditingScene(wizard)

    message = AsyncMock()
    await scene.on_enter(message, state, repository, [1, 2])

    message.answer.assert_called_once()
    args = message.answer.await_args.args
    for substring in ['A', 'B', 'About something', 'Alternative point']:
        assert substring in args[0]

    message = AsyncMock(text='B')
    message.from_user.id = 42
    await scene.on_message(message, state, repository)

    wizard.retake.assert_called_once()
    kwargs = wizard.retake.await_args.kwargs
    assert kwargs['slots'] == [2]
    async with repository.get_session() as session:
        result = await session.scalars(select(Selection))
        selection = result.one()
        assert selection.attendee == 42
        assert selection.time_slot_id == 1
        assert selection.speech_id == 3


@pytest.mark.asyncio
async def test_edit_remove(repository: Repository, state: StateFake):
    async with repository.get_session() as session:
        session.add(Selection(attendee=42, time_slot_id=1, speech_id=1))
        await session.commit()
    wizard = AsyncMock()
    scene = EditingScene(wizard)

    message = AsyncMock()
    await scene.on_enter(message, state, repository, [1, 2])

    message.answer.assert_called_once()
    args = message.answer.await_args.args
    for substring in ['A', 'B', 'About something', 'Alternative point']:
        assert substring in args[0]

    message = AsyncMock(text='Ничего')
    message.from_user.id = 42
    await scene.on_message(message, state, repository)

    wizard.retake.assert_called_once()
    kwargs = wizard.retake.await_args.kwargs
    assert kwargs['slots'] == [2]
    async with repository.get_session() as session:
        result = await session.scalars(select(Selection))
        assert result.first() is None


@pytest.mark.asyncio
async def test_edit_wrong(repository: Repository, state: StateFake):
    async with repository.get_session() as session:
        session.add(Selection(attendee=42, time_slot_id=1, speech_id=1))
        await session.commit()
    wizard = AsyncMock()
    scene = EditingScene(wizard)

    message = AsyncMock()
    await scene.on_enter(message, state, repository, [1, 2])

    message.answer.assert_called_once()
    args = message.answer.await_args.args
    for substring in ['A', 'B', 'About something', 'Alternative point']:
        assert substring in args[0]

    message = AsyncMock(text='C')
    message.from_user.id = 42
    await scene.on_message(message, state, repository)

    message.answer.assert_called_once()
    args = message.answer.await_args.args
    assert 'повторите' in args[0]


@pytest.mark.asyncio
async def test_edit_end(repository: Repository, state: StateFake):
    async with repository.get_session() as session:
        session.add(Selection(attendee=42, time_slot_id=1, speech_id=1))
        await session.commit()
    wizard = AsyncMock()
    scene = EditingScene(wizard)

    message = AsyncMock()
    await scene.on_enter(message, state, repository, [])

    message.answer.assert_called_once()
    args = message.answer.await_args.args
    assert 'Готово' in args[0]
    wizard.exit.assert_called_once()
