import asyncio
import logging
import logging.config
import os
import secrets
from collections.abc import Awaitable, Callable, Iterable
from logging.handlers import QueueHandler, QueueListener
from pathlib import Path
from queue import SimpleQueue
from typing import Any

from aiogram import Bot, Dispatcher
from aiogram.types import FSInputFile
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from aiohttp import web
from apscheduler.schedulers.asyncio import AsyncIOScheduler  # type: ignore
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import data.mock_data
import data.setup
import handlers.admin
import handlers.general
import handlers.middleware
import handlers.personal_edit
import handlers.personal_view
import handlers.settings
from data.repository import SelectionRepository, SpeechRepository, UserRepository
from dto import TimeSlotDto
from notifications import changed, event_start
from utility import FileManager


def configure_async_logging():
    root_logger = logging.getLogger()
    root_handlers = root_logger.handlers.copy()
    root_logger.handlers.clear()
    queue: SimpleQueue[Any] = SimpleQueue()
    root_logger.addHandler(QueueHandler(queue))
    listener = QueueListener(queue, *root_handlers)
    listener.start()
    return listener


async def main():
    log_config_path = Path(os.getenv('LOG_CONFIG', 'logging.ini'))
    if log_config_path.exists():
        logging.config.fileConfig(log_config_path)
    else:
        logging.basicConfig(level=logging.DEBUG)
    token = os.getenv('TELEGRAM_TOKEN')
    logger = logging.getLogger(__name__)
    if token is None:
        logger.critical('Token environment variable not found')
        return
    listener = configure_async_logging()
    try:
        await setup_and_run_bot(token, logger)
    finally:
        listener.stop()


async def setup_and_run_bot(token: str, logger: logging.Logger):
    engine = create_async_engine(os.getenv('DATABASE_URL', 'sqlite+aiosqlite:///:memory:'))
    session_maker = async_sessionmaker(engine)
    await data.setup.create_tables(engine)
    if os.getenv('FILL_MOCK_DATA') == '1':
        await data.mock_data.fill_tables(session_maker)

    speech_repository = SpeechRepository(session_maker)
    selection_repository = SelectionRepository(session_maker)
    user_repository = UserRepository(session_maker)
    general_schedule_path = Path(os.getenv('GENERAL_SCHEDULE_PATH', 'files/general.pdf'))
    file_manager = FileManager({handlers.general.SCHEDULE_FILE_KEY: general_schedule_path})

    bot = Bot(token)
    dispatcher = Dispatcher(speech_repository=speech_repository, selection_repository=selection_repository,
                            user_repository=user_repository, file_manager=file_manager)
    dispatcher.include_router(handlers.general.get_router())
    dispatcher.include_router(handlers.personal_view.get_router())
    dispatcher.include_router(handlers.settings.get_router())
    dispatcher.include_router(handlers.admin.get_router())
    handlers.personal_edit.init(dispatcher)
    handlers.middleware.init_middleware(dispatcher)

    scheduler = AsyncIOScheduler()

    def scheduler_callback():
        return event_start.configure_events(scheduler, speech_repository, selection_repository,
                                            bot, 5)
    await scheduler_callback()
    scheduler.start()

    async def change_callback(slots: Iterable[TimeSlotDto]):
        await scheduler_callback()
        await changed.notify_schedule_change(bot, selection_repository, slots)

    webhook_url = os.getenv('WEBHOOK_URL')
    if webhook_url:
        await run_webhook(bot, dispatcher, change_callback, webhook_url)
    else:
        logger.info('Starting polling')
        await dispatcher.start_polling(bot, schedule_update_callback=change_callback)  # type: ignore


async def run_webhook(bot: Bot, dispatcher: Dispatcher,
                      change_callback: Callable[[Iterable[TimeSlotDto]], Awaitable[Any]], webhook_url: str):
    logger = logging.getLogger(__name__)
    logger.info('Setting up webhook on %s', webhook_url)
    webhook_host = os.getenv('WEBHOOK_HOST', '127.0.0.1')
    webhook_port = int(os.getenv('WEBHOOK_PORT', '8080'))
    webhook_path = os.getenv('WEBHOOK_PATH', '/webhook')
    webhook_secret = secrets.token_urlsafe(64)
    handler = SimpleRequestHandler(dispatcher, bot, secret_token=webhook_secret,
                                   schedule_update_callback=change_callback)
    app = web.Application()
    handler.register(app, path=webhook_path)
    setup_application(app, dispatcher)
    certificate_path = os.getenv('WEBHOOK_CERT')
    certificate_file = FSInputFile(certificate_path) if certificate_path else None
    await bot.set_webhook(webhook_url + webhook_path, certificate_file, secret_token=webhook_secret)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, webhook_host, webhook_port)
    await site.start()
    logger.info('Webhook server started')
    try:
        await asyncio.Future()
    except (KeyboardInterrupt, asyncio.CancelledError):
        logger.info('Stopping webhook server')
    finally:
        await site.stop()
        await runner.cleanup()
        await bot.delete_webhook()


if __name__ == '__main__':
    asyncio.run(main())
