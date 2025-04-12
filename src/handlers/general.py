import datetime
import itertools
import logging
import textwrap

from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InaccessibleMessage, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder

from data.repository import Repository
from view import timetable


async def handle_start(message: Message, state: FSMContext):
    logging.getLogger(__name__).debug('User %s started interacting with the bot', message.from_user)
    builder = ReplyKeyboardBuilder().button(
        text='/list').button(text='/configure')
    await state.clear()
    await message.answer(textwrap.dedent('''
    Это бот, предоставляющий информацию о мероприятиях. Команды:
    /schedule - список всех мероприятий
    /configure - настройка персональной программы
    /personal - ваша персональная программа
        '''), reply_markup=builder.as_markup())


def handle_schedule(message: Message):
    keyboard = (InlineKeyboardBuilder()
                .button(text='Всё', callback_data='show_general_all')
                .button(text='Сегодня', callback_data='show_general_today')
                .button(text='Завтра', callback_data='show_general_tomorrow'))
    return message.answer('Какую часть расписания хотите просмотреть?', reply_markup=keyboard.as_markup())


async def handle_schedule_selection(callback: CallbackQuery, repository: Repository):
    message = callback.message
    if message is None or isinstance(message, InaccessibleMessage):
        await callback.answer('Сообщение устарело')
        return
    query = callback.data
    match query:
        case 'show_general_all':
            date = None
        case 'show_general_today':
            date = datetime.date.today()
        case 'show_general_tomorrow':
            date = datetime.date.today() + datetime.timedelta(days=1)
        case _:
            logging.getLogger(__name__).error('Received unknown general command %s', query)
            await callback.answer('Что-то пошло не так')
            return
    speeches = await repository.get_all_speeches(date)
    days = ((day, itertools.groupby(locations, lambda x: x.location))
            for day, locations in itertools.groupby(speeches, lambda x: x.time_slot.date))
    await callback.answer()
    await message.answer(timetable.render_timetable(days, date is None))


def get_router():
    router = Router()
    router.message.register(handle_start, CommandStart())
    router.message.register(handle_schedule, Command('schedule'))
    router.callback_query.register(
        handle_schedule_selection, F.data.startswith('show_general_'))
    logging.getLogger(__name__).info('General handlers registered')
    return router
