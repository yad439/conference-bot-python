import datetime
import itertools
from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, InaccessibleMessage, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder

from view import timetable

from data.repository import Repository


async def handle_personal_view(message: Message):
    keyboard = (InlineKeyboardBuilder()
                .button(text='Всё', callback_data='show_personal_all')
                .button(text='Сегодня', callback_data='show_personal_today')
                .button(text='Завтра', callback_data='show_personal_tomorrow'))
    await message.answer('Какую часть расписания хотите просмотреть?', reply_markup=keyboard.as_markup())


async def handle_personal_view_selection(callback: CallbackQuery, repository: Repository):
    message = callback.message
    if message is None or isinstance(message, InaccessibleMessage):
        await callback.answer('Сообщение устарело')
        return
    query = callback.data
    match query:
        case 'show_personal_all':
            date = None
        case 'show_personal_today':
            date = datetime.date.today()
        case 'show_personal_tomorrow':
            date = datetime.date.today() + datetime.timedelta(days=1)
        case _:
            raise ValueError('Unknown command')
    speeches = await repository.get_selected_speeches(callback.from_user.id, date)
    await callback.answer()
    if not speeches:
        await message.answer('Вы не выбрали ни одной записи')
        return
    days = itertools.groupby(speeches, lambda x: x.time_slot.date)
    await message.answer(timetable.render_personal(days))


def get_router():
    router = Router()
    router.message.register(handle_personal_view, Command('personal'))
    router.callback_query.register(
        handle_personal_view_selection, F.data.startswith('show_personal_'))
    return router
