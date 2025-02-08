import datetime
import logging

from sqlalchemy import insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from .tables import Speech, TimeSlot


async def fill_tables(session_factory: async_sessionmaker[AsyncSession]):
    async with session_factory() as session:
        id_result = await session.execute(insert(TimeSlot).returning(TimeSlot.id), [
            {'date': datetime.date(2025, 6, 1), 'start_time': datetime.time(
                9, 0), 'end_time': datetime.time(10, 0)},
            {'date': datetime.date(2025, 6, 1), 'start_time': datetime.time(
                10, 0), 'end_time': datetime.time(11, 0)},
        ])
        ids = id_result.scalars().all()
        await session.execute(insert(Speech), [
            {'title': 'About something', 'speaker': 'Dr. John Doe',
                'time_slot_id': ids[0], 'location': 'A'},
            {'title': 'About something else', 'speaker': 'Jane Doe',
             'time_slot_id': ids[1], 'location': 'A'},
            {'title': 'Alternative point', 'speaker': 'Mr. Alternative',
             'time_slot_id': ids[0], 'location': 'B'},
        ])
        await session.commit()
    logging.info('Tables filled with mock data')
