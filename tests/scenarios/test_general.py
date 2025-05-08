import pytest
import pytest_asyncio
from freezegun import freeze_time
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import data.mock_data
import data.setup
from data.repository import Repository
from handlers import general
from tests.FakeBot import BotFake


@pytest_asyncio.fixture  # type: ignore
async def repository():
    engine = create_async_engine('sqlite+aiosqlite:///:memory:')
    session_maker = async_sessionmaker(engine)
    await data.setup.create_tables(engine)
    await data.mock_data.fill_tables(session_maker)
    return Repository(session_maker)


@pytest.fixture
def bot(repository: Repository):
    bot = BotFake(repository=repository)
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
@pytest.mark.parametrize('query', ('show_general_today', 'show_general_tomorrow'))
async def test_schedule_empty(bot: BotFake, query: str):
    message = await _init_general(bot)

    await bot.query(message, query)

    assert not bot.pending_queries
    assert len(bot.sent_messages) == 2
    text = bot.sent_messages[1]
    assert 'Ничего' in text
