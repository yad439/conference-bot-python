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


async def handle_start(message: Message, state: FSMContext):
    _LOGGER.debug('User %s started interacting with the bot', format_user(message.from_user))
    builder = (ReplyKeyboardBuilder()
               .button(text='/schedule')
               .button(text='/configure')
               .button(text='/personal')
               .button(text='/settings'))
    await state.clear()
    await message.answer(textwrap.dedent('''
    Это бот, предоставляющий информацию о мероприятиях. Команды:
    /schedule - список всех мероприятий
    /configure - настройка персональной программы
    /personal - ваша персональная программа
    /settings - настройки уведомлений
        '''), reply_markup=builder.as_markup())


async def handle_schedule(message: Message):
    keyboard = (InlineKeyboardBuilder()
                .button(text='Всё', callback_data='show_general_all')
                .button(text='Сегодня', callback_data='show_general_today')
                .button(text='Завтра', callback_data='show_general_tomorrow'))
    return await message.answer('Какую часть расписания хотите просмотреть?', reply_markup=keyboard.as_markup())


async def handle_schedule_selection(callback: CallbackQuery, speech_repository: SpeechRepository,
                                    file_manager: FileManager):
    message = callback.message
    if message is None or isinstance(message, InaccessibleMessage):
        await callback.answer('Сообщение устарело')
        return
    query = callback.data
    timezone = ZoneInfo('Asia/Novosibirsk')
    _LOGGER.debug('User %s requested general schedule with query %s', format_user(callback.from_user), query)
    match query:
        case 'show_general_all':
            await _send_full_schedule(message, file_manager)
            await callback.answer()
            return
        case 'show_general_today':
            date = datetime.datetime.now(timezone).date()
        case 'show_general_tomorrow':
            date = datetime.datetime.now(timezone).date() + datetime.timedelta(days=1)
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
        await message.answer(timetable.render_timetable(days, False))


async def _send_full_schedule(message: Message, file_manager: FileManager):
    file_id = file_manager.get_file_id(SCHEDULE_FILE_KEY)
    if file_id is None:
        file = FSInputFile(file_manager.get_file_path(SCHEDULE_FILE_KEY))
        result = await message.answer_document(file)
        document = result.document
        assert document is not None
        file_manager.set_file_id(SCHEDULE_FILE_KEY, document.file_id)
    else:
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
