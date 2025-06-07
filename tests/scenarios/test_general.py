# ruff: noqa: PLR2004

import pytest
import pytest_asyncio
from freezegun import freeze_time
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

import data.mock_data
import data.setup
from data.repository import SpeechRepository, UserRepository
from data.tables import Settings
from handlers import general
from tests.fake_bot import BotFake


@pytest_asyncio.fixture  # type: ignore
async def session_maker():
    engine = create_async_engine('sqlite+aiosqlite:///:memory:')
    session_maker = async_sessionmaker(engine)
    await data.setup.create_tables(engine)
    await data.mock_data.fill_tables(session_maker)
    return session_maker


@pytest.fixture
def speech_repository(session_maker: async_sessionmaker[AsyncSession]):
    return SpeechRepository(session_maker)


@pytest.fixture
def user_repository(session_maker: async_sessionmaker[AsyncSession]):
    return UserRepository(session_maker)


@pytest.fixture
def bot(speech_repository: SpeechRepository, user_repository: UserRepository):
    bot = BotFake(speech_repository=speech_repository, user_repository=user_repository)
    bot.router.include_router(general.get_router())
    return bot


@pytest.mark.asyncio
async def test_start(bot: BotFake):
    await bot.message('/start')

    assert len(bot.sent_messages) == 1
    text = bot.sent_messages[0]
    assert '/configure' in text
    assert '/schedule' in text
    assert '/personal' in text


async def _init_general(bot: BotFake):
    await bot.message('/schedule')

    assert len(bot.sent_messages) == 1
    text = bot.sent_messages[0]
    assert 'Какую часть расписания' in text

    return bot.messages[-1]


@pytest.mark.asyncio
async def test_general_all(bot: BotFake):
    message = await _init_general(bot)

    await bot.query(message, 'show_general_all')

    assert not bot.pending_queries
    assert len(bot.sent_messages) == 2
    text = bot.sent_messages[1]
    for substring in ('About something', 'About something else', 'Alternative point', 'New day talk',
                      'Alternative day 2', 'Dr. John Doe', 'Jane Doe', 'Mr. Alternative', 'New speaker', 'A', 'B',
                      '01.06', '02.06', '9:00', '10:00', '11:00'):
        assert substring in text


@pytest.mark.asyncio
@freeze_time('2025-06-01')
async def test_general_today(bot: BotFake):
    message = await _init_general(bot)

    await bot.query(message, 'show_general_today')

    assert not bot.pending_queries
    assert len(bot.sent_messages) == 2
    text = bot.sent_messages[1]
    for substring in ('About something', 'About something else', 'Alternative point', 'Dr. John Doe', 'Jane Doe',
                      'Mr. Alternative', 'A', 'B', '01.06', '9:00', '10:00', '11:00'):
        assert substring in text
    for substring in 'New day talk', 'Alternative day 2', 'New speaker', '02.06':
        assert substring not in text


@pytest.mark.asyncio
@freeze_time('2025-06-01')
async def test_general_tomorrow(bot: BotFake):
    message = await _init_general(bot)

    await bot.query(message, 'show_general_tomorrow')

    assert not bot.pending_queries
    assert len(bot.sent_messages) == 2
    text = bot.sent_messages[1]
    for substring in ('New day talk', 'Alternative day 2', 'Mr. Alternative', 'New speaker', 'A', 'B', '02.06', '9:00',
                      '10:00'):
        assert substring in text
    for substring in ('About something', 'About something else', 'Alternative point', 'Dr. John Doe', 'Jane Doe',
                      '01.06', '11:00'):
        assert substring not in text


@pytest.mark.asyncio
@freeze_time('2025-05-01')
@pytest.mark.parametrize('query', ['show_general_today', 'show_general_tomorrow'])
async def test_schedule_empty(bot: BotFake, query: str):
    message = await _init_general(bot)

    await bot.query(message, query)

    assert not bot.pending_queries
    assert len(bot.sent_messages) == 2
    text = bot.sent_messages[1]
    assert 'Ничего' in text


@pytest.mark.asyncio
@pytest.mark.parametrize('present', [True, False])
@pytest.mark.parametrize('state', ['not present', 'registered', 'without username'])
async def test_register(bot: BotFake, session_maker: async_sessionmaker[AsyncSession], present: bool, state: str):
    if state != 'not present':
        async with session_maker() as session, session.begin():
            session.add(Settings(user_id=42, username='testUser') if present else Settings(user_id=42))

    await bot.message('/register', username='testUser' if present else None)

    assert len(bot.sent_messages) == 1
    assert ('Успех' if present else 'не задано') in bot.sent_messages[0]
    if present:
        async with session_maker() as session:
            result = await session.scalars(select(Settings))
            setting = result.one()
            assert setting.user_id == 42
            assert setting.username == 'testUser'
