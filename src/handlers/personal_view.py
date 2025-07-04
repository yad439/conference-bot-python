import datetime
import itertools
import logging
from zoneinfo import ZoneInfo

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, InaccessibleMessage, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder

from data.repository import SelectionRepository
from utility import format_user
from view import timetable

_LOGGER = logging.getLogger(__name__)


async def handle_personal_view(message: Message):
    keyboard = (InlineKeyboardBuilder()
                .button(text='Всё', callback_data='show_personal_all')
                .button(text='Сегодня', callback_data='show_personal_today')
                .button(text='Завтра', callback_data='show_personal_tomorrow'))
    await message.answer('Какую часть расписания хотите просмотреть?', reply_markup=keyboard.as_markup())


async def handle_personal_view_selection(callback: CallbackQuery, selection_repository: SelectionRepository):
    message = callback.message
    if message is None or isinstance(message, InaccessibleMessage):
        _LOGGER.warning('Received callback for an inaccessible message from user %s', format_user(callback.from_user))
        await callback.answer('Сообщение устарело')
        return
    query = callback.data
    timezone = ZoneInfo('Asia/Novosibirsk')
    _LOGGER.debug('User %s requested personal schedule with query %s', format_user(callback.from_user), query)
    match query:
        case 'show_personal_all':
            date = None
        case 'show_personal_today':
            date = datetime.datetime.now(timezone).date()
        case 'show_personal_tomorrow':
            date = datetime.datetime.now(timezone).date() + datetime.timedelta(days=1)
        case _:
            _LOGGER.error('Received unknown personal command %s', query)
            await callback.answer('Что-то пошло не так')
            return
    speeches = await selection_repository.get_selected_speeches(callback.from_user.id, date)
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
