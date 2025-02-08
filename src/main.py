import logging
from pathlib import Path
from aiogram import Bot, Dispatcher
import os

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import database.mock_data
from database.repository import SpeechRepository
import handlers.general
import database.setup


async def main():
    logging.basicConfig(level=logging.DEBUG)
    TOKEN = os.getenv('TELEGRAM_TOKEN')
    if TOKEN is None:
        logging.critical('Token environment variable not found')
        return
    new_database = not Path('db.sqlite').exists()
    engine = create_async_engine('sqlite+aiosqlite:///db.sqlite')
    session_maker = async_sessionmaker(engine)
    if new_database:
        await database.setup.create_tables(engine)
        await database.mock_data.fill_tables(session_maker)
    speech_repository = SpeechRepository(session_maker)
    bot = Bot(TOKEN)
    dispatcher = Dispatcher(speech_repository=speech_repository)
    dispatcher.include_router(handlers.general.get_router())
    logging.info('Starting polling')
    await dispatcher.start_polling(bot)  # type: ignore

if __name__ == '__main__':
    import asyncio
    asyncio.run(main())
