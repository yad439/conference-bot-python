import itertools
import logging
import textwrap
from aiogram import Router
from aiogram.filters import Command, CommandStart
from aiogram.types import Message
from aiogram.utils import keyboard
from aiogram.fsm.context import FSMContext

from data.repository import Repository
from view import timetable


async def handle_start(message: Message, state: FSMContext):
    builder = keyboard.ReplyKeyboardBuilder().button(
        text='/list').button(text='/configure')
    await state.clear()
    await message.answer(textwrap.dedent('''
    Это бот, предоставляющий информацию о мероприятиях. Команды:
    /list - список всех мероприятий
    /configure - настройка персональной программы
    /personal - ваша персональная программа
        '''), reply_markup=builder.as_markup())


async def handle_list(message: Message, repository: Repository):
    speeches = await repository.get_all_speeches()
    days = ((day, itertools.groupby(locations, lambda x: x.location))
            for day, locations in itertools.groupby(speeches, lambda x: x.time_slot.date))
    await message.answer(timetable.render_timetable(days))


def get_router():
    router = Router()
    router.message(CommandStart())(handle_start)
    router.message(Command('list'))(handle_list)
    logging.getLogger(__name__).info('General handlers registered')
    return router
