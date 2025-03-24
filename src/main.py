import logging
import os

from aiogram import Bot, Dispatcher
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import data.mock_data
import data.setup
import handlers.general
import handlers.personal_edit
import handlers.personal_view
from data.repository import Repository


async def main():
    logging.basicConfig(level=logging.DEBUG)
    token = os.getenv('TELEGRAM_TOKEN')
    if token is None:
        logging.critical('Token environment variable not found')
        return
    engine = create_async_engine('sqlite+aiosqlite:///:memory:')
    session_maker = async_sessionmaker(engine)
    await data.setup.create_tables(engine)
    await data.mock_data.fill_tables(session_maker)
    speech_repository = Repository(session_maker)
    bot = Bot(token)
    dispatcher = Dispatcher(repository=speech_repository)
    dispatcher.include_router(handlers.general.get_router())
    dispatcher.include_router(handlers.personal_view.get_router())
    handlers.personal_edit.init(dispatcher)
    logging.info('Starting polling')
    await dispatcher.start_polling(bot)  # type: ignore

if __name__ == '__main__':
    import asyncio
    asyncio.run(main())
