import logging
from pathlib import Path
from aiogram import Bot, Dispatcher
import os

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import data.mock_data
from data.repository import Repository
import handlers.general
import handlers.personal
import data.setup


async def main():
    logging.basicConfig(level=logging.DEBUG)
    token = os.getenv('TELEGRAM_TOKEN')
    if token is None:
        logging.critical('Token environment variable not found')
        return
    new_database = not Path('db.sqlite').exists()
    engine = create_async_engine('sqlite+aiosqlite:///db.sqlite')
    session_maker = async_sessionmaker(engine)
    if new_database:
        await data.setup.create_tables(engine)
        await data.mock_data.fill_tables(session_maker)
    speech_repository = Repository(session_maker)
    bot = Bot(token)
    dispatcher = Dispatcher(repository=speech_repository)
    dispatcher.include_router(handlers.general.get_router())
    handlers.personal.init(dispatcher)
    logging.info('Starting polling')
    await dispatcher.start_polling(bot)  # type: ignore

if __name__ == '__main__':
    import asyncio
    asyncio.run(main())
