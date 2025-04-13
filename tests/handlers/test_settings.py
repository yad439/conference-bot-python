import datetime
from unittest.mock import AsyncMock

import pytest
import pytest_asyncio
from aiogram.types import Chat, Message
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import data.mock_data
import data.setup
from data.repository import Repository
from data.tables import Settings
from handlers import settings


@pytest_asyncio.fixture  # type: ignore
async def repository():
    engine = create_async_engine('sqlite+aiosqlite:///:memory:')
    session_maker = async_sessionmaker(engine)
    await data.setup.create_tables(engine)
    await data.mock_data.fill_tables(session_maker)
    async with session_maker() as session, session.begin():
        session.add_all((Settings(user_id=41, notifications_enabled=True),
                         Settings(user_id=42, notifications_enabled=False)))
    return Repository(session_maker)


@pytest.mark.asyncio
@pytest.mark.parametrize('user,expected', [(41, True), (42, False), (43, True)])
async def test_handle_settings(repository: Repository, user: int, expected: bool):
    message = AsyncMock(text='/settings')
    message.from_user.id = user

    await settings.handle_show_settings(message, repository)

    message.answer.assert_awaited_once()
    args = message.answer.await_args[0]
    if expected:
        assert 'Уведомления включены' in args[0]
    else:
        assert 'Уведомления выключены' in args[0]


@pytest.mark.asyncio
@pytest.mark.parametrize('user,option', [(41, True), (42, True), (43, True), (41, False), (42, False), (43, False)])
async def test_handle_change_settings(repository: Repository, user: int, option: bool):
    callback = AsyncMock(data='set_notifications_on' if option else 'set_notifications_off')
    callback.from_user.id = user
    callback.message = Message(message_id=1, date=datetime.datetime(2025, 1, 1),
                               chat=Chat(id=1, type='private')).as_(AsyncMock())

    await settings.handle_set_setting(callback, repository)

    callback.answer.assert_awaited_once()
    args = callback.answer.await_args[0]
    if option:
        assert 'Уведомления включены' in args[0]
    else:
        assert 'Уведомления выключены' in args[0]
