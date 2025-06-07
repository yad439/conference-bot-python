import dataclasses
import datetime
import logging
from collections.abc import Awaitable, Callable, Iterable, Mapping
from csv import DictReader
from io import TextIOWrapper
from typing import Any, TextIO
from zoneinfo import ZoneInfo

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message, TelegramObject
from sqlalchemy.exc import IntegrityError

from data.repository import Repository
from dto import SpeechDto, TimeSlotDto


def get_router():
    router = Router()
    router.message.register(set_admin_handler, Command('admin'))
    router.message.register(set_admin_handler, Command('unadmin'))
    router.message.register(modify_schedule_handler, Command('edit_schedule'))
    router.message.middleware(check_rights_middleware)
    return router


async def check_rights_middleware(handler: Callable[[Message, dict[str, Any]], Awaitable[Any]],
                                  event: TelegramObject, data: dict[str, Any]):
    repository: Repository = data['repository']
    assert isinstance(event, Message)
    user = event.from_user
    assert user is not None
    admin = await repository.is_admin(user.id)
    if admin:
        return await handler(event, data)
    return None


async def set_admin_handler(message: Message, repository: Repository):
    logger = logging.getLogger(__name__)
    text = message.text
    logger.debug('Processing admin command: %s', text)
    assert text is not None

    command = text.split(' ')
    if len(command) != 2:  # noqa: PLR2004
        await message.answer('Неверный формат команды. Используйте /admin или /unadmin <ID/username>')
        logger.warning('Invalid command format: %s', text)
        return

    make_admin = command[0] == '/admin'
    action_msg = 'Пользователь {} стал администратором' if make_admin else 'Пользователь {} больше не администратор'
    action_log = '%s became admin' if make_admin else '%s is no longer admin'

    identifier = command[1]
    if identifier.isdecimal():
        user_id = int(identifier)
        await repository.set_admin(user_id, make_admin)
        await message.answer(action_msg.format(user_id))
        logger.info(action_log, user_id)
    else:
        success = await repository.set_admin_by_username(identifier, make_admin)
        if success:
            await message.answer(action_msg.format(identifier))
            logger.info(action_log, identifier)
        else:
            await message.answer(f'Пользователь {identifier} не найден')
            logger.info('User %s not found for admin privileges', identifier)


async def modify_schedule_handler(message: Message, repository: Repository):
    logger = logging.getLogger(__name__)
    file = message.document
    if file is None or not file.file_name or not file.file_name.endswith('.csv'):
        if file is None:
            logger.warning('No file attached to the editing message')
        else:
            logger.warning('Invalid file format: %s', file.file_name)
        await message.answer('Пожалуйста, прикрепите файл в формате CSV')
        return
    bot = message.bot
    assert bot is not None
    file = await bot.download(file.file_id)
    assert file is not None
    text_io = TextIOWrapper(file, encoding='utf-8')
    try:
        slots, speeches, deletes = _parse_csv(text_io)
    except (ValueError, KeyError):
        logger.warning('Error parsing CSV file', exc_info=True)
        await message.answer('Ошибка при обработке файла')
        return
    try:
        async with repository.get_session() as session, session.begin():
            slot_mapping = await repository.find_or_create_slots(slots, session)
            if deletes:
                logger.info('Deleting %d speeches', len(deletes))
                to_delete = ((slot_mapping[entry[0].date, entry[0].start_time, entry[0].end_time], entry[1])
                             for entry in deletes)
                await repository.delete_speeches(to_delete, session)
            if speeches:
                logger.info('Updating %d speeches', len(speeches))
                speeches = _update_slots(speeches, slot_mapping)
                await repository.update_or_insert_speeches(speeches, session)
    except IntegrityError as e:
        logger.exception('Database integrity error')
        await message.answer(f'Ошибка при обновлении расписания: {e.orig}')
        return
    await message.answer('Расписание обновлено')
    logger.info('Schedule updated with %d speeches and %d deletes', len(speeches), len(deletes))


def _parse_csv(data: TextIO):
    slots: dict[tuple[str, str, str], TimeSlotDto] = {}
    speeches: list[SpeechDto] = []
    deletes: list[tuple[TimeSlotDto, str]] = []
    timezone = ZoneInfo('Asia/Novosibirsk')
    for row in DictReader(data):
        date = row['date']
        start_time = row['start_time']
        end_time = row['end_time']
        if (date, start_time, end_time) not in slots:
            slots[date, start_time, end_time] = TimeSlotDto(None, _parse_date(
                date), _parse_time(start_time, timezone), _parse_time(end_time, timezone))
        slot = slots[date, start_time, end_time]
        title = row['title']
        if not title:
            deletes.append((slot, row['location']))
        else:
            speech = SpeechDto(None, row['title'], row['speaker'], slot, row['location'])
            speeches.append(speech)
    return slots.values(), speeches, deletes


def _parse_date(date_str: str, year: int = 2025):
    return datetime.datetime.strptime(f'{date_str}-{year}', '%d-%m-%Y').replace(tzinfo=datetime.UTC).date()


def _parse_time(time_str: str, timezone: datetime.tzinfo):
    return datetime.datetime.strptime(time_str, '%H:%M').replace(tzinfo=timezone).timetz()


def _update_slots(speeches: Iterable[SpeechDto],
                  slot_mapping: Mapping[tuple[datetime.date, datetime.time, datetime.time], int]):
    slots = frozenset(speech.time_slot for speech in speeches)
    mapping = {old_slot: dataclasses.replace(
        old_slot, id=slot_mapping[old_slot.date, old_slot.start_time, old_slot.end_time]) for old_slot in slots}
    return [dataclasses.replace(speech, time_slot=mapping[speech.time_slot])
            for speech in speeches]
