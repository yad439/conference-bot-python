import datetime
import textwrap
from zoneinfo import ZoneInfo

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.orm import selectinload

import data.mock_data
import data.setup
from data.repository import Repository
from data.tables import Settings, Speech
from handlers import admin
from tests.fake_bot import BotFake


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
@pytest.mark.parametrize('command', ['/admin 43', '/unadmin 42', '/edit_schedule'])
async def test_access_denied(bot: BotFake, command: str):
    await bot.message(command, user_id=43)

    assert len(bot.sent_messages) == 0


@pytest.mark.asyncio
@pytest.mark.parametrize('set_admin', [True, False])
@pytest.mark.parametrize(('target_user', 'target_id'), [('43', 43), ('44', 44), ('another_user', 43),
                                                        ('unknown_user', -1)])
@pytest.mark.parametrize('target_admin', [True, False, None])
async def test_set_admin(bot: BotFake, repository: Repository, set_admin: bool,  # noqa: PLR0913, PLR0917
                         target_user: str, target_id: int, target_admin: bool | None):
    async with repository.get_session() as session, session.begin():
        session.add(Settings(user_id=43, username='another_user', admin=target_admin))

    await bot.message(f'/admin {target_user}' if set_admin else f'/unadmin {target_user}', user_id=42)

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


@pytest.mark.asyncio
async def test_set_admin_invalid_format(bot: BotFake):
    await bot.message('/admin 42 a')

    assert len(bot.sent_messages) == 1
    text = bot.sent_messages[0]
    assert 'Неверный формат' in text


@pytest.mark.asyncio
async def test_update_schedule(bot: BotFake, repository: Repository):
    bot.router.include_router(admin.get_router())
    data = '''
    date,start_time,end_time,location,title,speaker
    01-06,09:00,10:00,A,About something else,Jane Doe
    01-06,10:00,11:00,A,About something,Dr. John Doe
    01-06,09:00,10:00,B,Alternative day 2,Mr. Alternative
    02-06,09:00,10:00,B,,
    02-06,10:00,11:00,A,"New day talk, extended",New speaker
    '''
    data = textwrap.dedent(data).strip()

    await bot.message('/edit_schedule', user_id=42, file=('schedule.csv', data.encode('utf-8')))

    assert len(bot.sent_messages) == 1
    assert 'Расписание обновлено' in bot.sent_messages[0]
    timezone = ZoneInfo('Asia/Novosibirsk')
    slots = (
        (datetime.date(2025, 6, 1), datetime.time(9, tzinfo=timezone), datetime.time(10, tzinfo=timezone)),
        (datetime.date(2025, 6, 1), datetime.time(10, tzinfo=timezone), datetime.time(11, tzinfo=timezone)),
        (datetime.date(2025, 6, 2), datetime.time(9, tzinfo=timezone), datetime.time(10, tzinfo=timezone)),
        (datetime.date(2025, 6, 2), datetime.time(10, tzinfo=timezone), datetime.time(11, tzinfo=timezone)),
    )
    reference_schedule = (
        (*slots[0], 'A', 'About something else', 'Jane Doe'),
        (*slots[1], 'A', 'About something', 'Dr. John Doe'),
        (*slots[0], 'B', 'Alternative day 2', 'Mr. Alternative'),
        (*slots[2], 'A', 'New day talk', 'New speaker'),
        (*slots[3], 'A', 'New day talk, extended', 'New speaker'),
    )
    async with repository.get_session() as session:
        result = await session.scalars(select(Speech).options(selectinload(Speech.time_slot)))
        schedule = result.all()
        assert len(schedule) == len(reference_schedule)
        for speech in reference_schedule:
            assert any(
                speech == (
                    s.time_slot.date,
                    s.time_slot.start_time,
                    s.time_slot.end_time,
                    s.location,
                    s.title,
                    s.speaker) for s in schedule)


@pytest.mark.asyncio
async def test_update_schedule_no_file(bot: BotFake):
    bot.router.include_router(admin.get_router())

    await bot.message('/edit_schedule', user_id=42)

    assert len(bot.sent_messages) == 1
    assert 'прикрепите файл' in bot.sent_messages[0]


@pytest.mark.asyncio
async def test_update_schedule_not_csv(bot: BotFake):
    bot.router.include_router(admin.get_router())

    await bot.message('/edit_schedule', user_id=42, file=('schedule.txt', b'something'))

    assert len(bot.sent_messages) == 1
    assert 'прикрепите файл' in bot.sent_messages[0]


@pytest.mark.asyncio
@pytest.mark.parametrize('wrong_header', [True, False])
async def test_update_schedule_wrong_format(bot: BotFake, wrong_header: bool):
    bot.router.include_router(admin.get_router())
    if wrong_header:
        data = '''
        date,start_time,end_tim,location,title,speaker
        01-06,09:00,10:00,A,About something else,Jane Doe
        '''
    else:
        data = '''
        date,start_time,end_time,location,title,speaker
        01,09:00,10:00,A,About something else,Jane Doe
        '''

    await bot.message('/edit_schedule', user_id=42, file=('schedule.csv', data.encode('utf-8')))

    assert len(bot.sent_messages) == 1
    assert 'Ошибка' in bot.sent_messages[0]
