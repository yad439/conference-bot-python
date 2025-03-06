from collections import Counter
import pytest
from unittest.mock import AsyncMock

import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import data.mock_data
import data.setup
from data.repository import Repository

from handlers import personal
from handlers.general import EditIntentionScene


@pytest_asyncio.fixture(loop_scope='function')  # type: ignore
async def repository():
    engine = create_async_engine('sqlite+aiosqlite:///:memory:')
    session_maker = async_sessionmaker(engine)
    await data.setup.create_tables(engine)
    await data.mock_data.fill_tables(session_maker)
    return Repository(session_maker)


@pytest.mark.asyncio
async def test_editing_intent_all(repository: Repository):
    wizard = AsyncMock()
    scene = EditIntentionScene(wizard)

    message = AsyncMock()
    await scene.on_enter(message)

    message = AsyncMock()
    message.text = 'Все'
    await scene.on_message(message, repository)

    wizard.goto.assert_called_once()
    args = wizard.goto.await_args.args
    kargs = wizard.goto.await_args.kwargs
    assert args[0] == personal.EditingScene
    assert Counter(kargs['slots']) == Counter(range(1, 4))


@pytest.mark.asyncio
async def test_editing_intent_day(repository: Repository):
    wizard = AsyncMock()
    scene = EditIntentionScene(wizard)

    message = AsyncMock()
    await scene.on_enter(message)

    message = AsyncMock()
    message.text = 'День'
    await scene.on_message(message, repository)

    wizard.goto.assert_called_once()
    args = wizard.goto.await_args.args
    assert args[0] == personal.SelectDayScene
