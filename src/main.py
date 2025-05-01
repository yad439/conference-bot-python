import logging
import os

from aiogram import Bot, Dispatcher
from apscheduler.schedulers.asyncio import AsyncIOScheduler  # type: ignore
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import data.mock_data
import data.setup
import handlers.general
import handlers.middleware
import handlers.personal_edit
import handlers.personal_view
import handlers.settings
from data.repository import Repository
from notifications import event_start


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
    repository = Repository(session_maker)

    bot = Bot(token)
    dispatcher = Dispatcher(repository=repository)
    dispatcher.include_router(handlers.general.get_router())
    dispatcher.include_router(handlers.personal_view.get_router())
    dispatcher.include_router(handlers.settings.get_router())
    handlers.personal_edit.init(dispatcher)
    handlers.middleware.init_middleware(dispatcher)

    scheduler = AsyncIOScheduler()
    await event_start.configure_events(scheduler, repository, bot, 5)
    scheduler.start()

    logging.info('Starting polling')
    await dispatcher.start_polling(bot)  # type: ignore

if __name__ == '__main__':
    import asyncio
    asyncio.run(main())
