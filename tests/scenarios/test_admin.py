import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import data.mock_data
import data.setup
from data.repository import Repository
from data.tables import Settings
from handlers import admin
from tests.FakeBot import BotFake


@pytest_asyncio.fixture  # type: ignore
async def repository():
    engine = create_async_engine('sqlite+aiosqlite:///:memory:')
    session_maker = async_sessionmaker(engine)
    await data.setup.create_tables(engine)
    await data.mock_data.fill_tables(session_maker)
    async with session_maker() as session, session.begin():
        session.add(Settings(user_id=42, admin=True))
    return Repository(session_maker)


@pytest.fixture
def bot(repository: Repository):
    bot = BotFake(repository=repository)
    bot.router.include_router(admin.get_router())
    return bot


@pytest.mark.asyncio
@pytest.mark.parametrize('is_admin', [True, False])
@pytest.mark.parametrize('set_admin', [True, False])
@pytest.mark.parametrize('target_user,target_id', [('43', 43), ('44', 44), ('another_user', 43), ('unknown_user', -1)])
@pytest.mark.parametrize('target_admin', [True, False, None])
async def test_set_admin(bot: BotFake, repository: Repository, is_admin: bool, set_admin: bool, target_user: str,
                         target_id: int, target_admin: bool | None):
    async with repository.get_session() as session, session.begin():
        session.add(Settings(user_id=43, username='another_user', admin=target_admin))

    await bot.message(f'/admin {target_user}' if set_admin else f'/unadmin {target_user}',
                      user_id=42 if is_admin else 41)

    if is_admin:
        assert len(bot.sent_messages) == 1
        text = bot.sent_messages[0]
        if target_user != 'unknown_user':
            if set_admin:
                assert 'стал администратором' in text
            else:
                assert 'больше не администратор' in text
            async with repository.get_session() as session:
                result = await session.scalars(select(Settings).where(Settings.user_id == target_id))
                assert result.one().admin == set_admin
        else:
            assert 'не найден' in text
    else:
        assert len(bot.sent_messages) == 0
        async with repository.get_session() as session:
            result = await session.scalars(select(Settings).where(Settings.user_id == target_id))
            if target_id == 43:
                assert result.one().admin == bool(target_admin)
            else:
                assert result.first() is None


@pytest.mark.asyncio
async def test_set_admin_invalid_format(bot: BotFake):
    await bot.message('/admin 42 a')

    assert len(bot.sent_messages) == 1
    text = bot.sent_messages[0]
    assert 'Неверный формат' in text
