import datetime
import itertools
import logging
import textwrap
from zoneinfo import ZoneInfo

from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, FSInputFile, InaccessibleMessage, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder

from data.repository import SpeechRepository, UserRepository
from utility import FileManager, format_user
from view import timetable

SCHEDULE_FILE_KEY = 'schedule'

_LOGGER = logging.getLogger(__name__)


def build_general_keyboard():
    builder = (ReplyKeyboardBuilder()
               .button(text='/schedule')
               .button(text='/configure')
               .button(text='/personal')
               .button(text='/settings'))
    return builder.as_markup()


async def handle_start(message: Message, state: FSMContext):
    _LOGGER.debug('User %s started interacting with the bot', format_user(message.from_user))
    await state.clear()
    sent_message = await message.answer(textwrap.dedent('''
    Это бот, предоставляющий информацию о мероприятиях. Команды:
    /schedule - список всех мероприятий
    /configure - настройка персональной программы
    /personal - ваша персональная программа
    /settings - настройки уведомлений
    /start - показать это сообщение, сбросить состояние и клавиатуру
        '''), reply_markup=build_general_keyboard())
    await sent_message.chat.unpin_all_messages()
    await sent_message.pin()


async def handle_schedule(message: Message, speech_repository: SpeechRepository):
    keyboard = (InlineKeyboardBuilder()
                .button(text='Всё', callback_data='show_general_all'))
    for date in await speech_repository.get_all_dates():
        keyboard.button(text=date.strftime('%d.%m'),
                        callback_data=f'show_general_date#{date.strftime('%Y-%m-%d:+0700')}')
    return await message.answer('Какую часть расписания хотите просмотреть?', reply_markup=keyboard.as_markup())


async def handle_schedule_selection(callback: CallbackQuery, speech_repository: SpeechRepository,
                                    file_manager: FileManager):
    message = callback.message
    if message is None or isinstance(message, InaccessibleMessage):
        await callback.answer('Сообщение устарело')
        return
    query = callback.data
    assert query is not None
    command = query.split('#')
    timezone = ZoneInfo('Asia/Novosibirsk')
    _LOGGER.debug('User %s requested general schedule with query %s', format_user(callback.from_user), query)
    match command[0]:
        case 'show_general_all':
            await _send_full_schedule(message, file_manager)
            await callback.answer()
            return
        case 'show_general_today':
            date = datetime.datetime.now(timezone).date()
        case 'show_general_tomorrow':
            date = datetime.datetime.now(timezone).date() + datetime.timedelta(days=1)
        case 'show_general_date':
            try:
                date = datetime.datetime.strptime(command[1], '%Y-%m-%d:%z').date()
            except (IndexError, ValueError):
                _LOGGER.exception('Invalid date format in command %s', query)
                await callback.answer('Что-то пошло не так')
                return
        case _:
            _LOGGER.error('Received unknown general command %s', query)
            await callback.answer('Что-то пошло не так')
            return
    speeches = await speech_repository.get_all_speeches(date)
    await callback.answer()
    if not speeches:
        await message.answer('Ничего не найдено')
    else:
        days = ((day, itertools.groupby(locations, lambda x: x.location))
                for day, locations in itertools.groupby(speeches, lambda x: x.time_slot.date))
        for text in timetable.render_timetable(days, False):
            await message.answer(**text.as_kwargs())


async def _send_full_schedule(message: Message, file_manager: FileManager):
    file_id = file_manager.get_file_id(SCHEDULE_FILE_KEY)
    if file_id is None:
        file = FSInputFile(file_manager.get_file_path(SCHEDULE_FILE_KEY))
        _LOGGER.info('Uploading file %s for schedule', file.path)
        result = await message.answer_document(file)
        document = result.document
        assert document is not None
        file_manager.set_file_id(SCHEDULE_FILE_KEY, document.file_id)
    else:
        _LOGGER.debug('Using cached file ID %s for schedule', file_id)
        await message.answer_document(file_id)


async def handle_register(message: Message, user_repository: UserRepository):
    user = message.from_user
    assert user is not None
    username = user.username
    if username is not None:
        await user_repository.register_user(user.id, username)
        await message.answer('Успех')
    else:
        await message.answer('Имя пользователя не задано')


def get_router():
    router = Router()
    router.message.register(handle_start, CommandStart())
    router.message.register(handle_schedule, Command('schedule'))
    router.callback_query.register(
        handle_schedule_selection, F.data.startswith('show_general_'))
    router.message.register(handle_register, Command('register'))
    _LOGGER.info('General handlers registered')
    return router
