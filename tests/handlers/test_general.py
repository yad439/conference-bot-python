import pytest
from unittest.mock import AsyncMock
import pytest_asyncio
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
    assert '/list' in args[0]


@pytest.mark.asyncio
async def test_list(repository: Repository):
    message = AsyncMock(text='/list')
    await general.handle_list(message, repository)

    message.answer.assert_called_once()
    args = message.answer.await_args.args
    for substring in ['About something', 'About something else', 'Alternative point', 'New day talk',
                      'Alternative day 2', 'Dr. John Doe', 'Jane Doe', 'Mr. Alternative', 'New speaker', 'A', 'B',
                      '01.06', '02.06', '9:00', '10:00', '11:00']:
        assert substring in args[0]
