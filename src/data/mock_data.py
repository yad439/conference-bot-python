import datetime
import logging
from zoneinfo import ZoneInfo

from sqlalchemy import insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from .tables import Speech, TimeSlot


async def fill_tables(session_factory: async_sessionmaker[AsyncSession]):
    async with session_factory() as session, session.begin():
        timezone = ZoneInfo('Asia/Novosibirsk')
        id_result = await session.execute(insert(TimeSlot).returning(TimeSlot.id), [
            {'date': datetime.date(2025, 6, 1), 'start_time': datetime.time(9, tzinfo=timezone),
             'end_time': datetime.time(10, tzinfo=timezone)},
            {'date': datetime.date(2025, 6, 1), 'start_time': datetime.time(10, tzinfo=timezone),
             'end_time': datetime.time(11, tzinfo=timezone)},
            {'date': datetime.date(2025, 6, 2), 'start_time': datetime.time(9, tzinfo=timezone),
             'end_time': datetime.time(10, tzinfo=timezone)},
        ])
        ids = id_result.scalars().all()
        await session.execute(insert(Speech), [
            {'title': 'About something', 'speaker': 'Dr. John Doe',
                'time_slot_id': ids[0], 'location': 'A'},
            {'title': 'About something else', 'speaker': 'Jane Doe',
             'time_slot_id': ids[1], 'location': 'A'},
            {'title': 'Alternative point', 'speaker': 'Mr. Alternative',
             'time_slot_id': ids[0], 'location': 'B'},
            {'title': 'New day talk', 'speaker': 'New speaker',
             'time_slot_id': ids[2], 'location': 'A'},
            {'title': 'Alternative day 2', 'speaker': 'Mr. Alternative',
             'time_slot_id': ids[2], 'location': 'B'},
        ])
    logging.getLogger(__name__).info('Tables filled with mock data')
