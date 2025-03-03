import logging
import textwrap
from aiogram import Router
from aiogram.filters import Command, CommandStart
from aiogram.types import Message
from aiogram.utils import keyboard
from aiogram.fsm.context import FSMContext

from data.repository import Repository
from view import timetable
from .personal import EditIntentionScene


async def handle_start(message: Message, state: FSMContext):
    builder = keyboard.ReplyKeyboardBuilder().button(
        text='/list').button(text='/configure')
    await state.clear()
    await message.answer(textwrap.dedent('''
    Это бот, предоставляющий информацию о мероприятиях. Команды:
    /list - список всех мероприятий
    /configure - настройка персональной программы
        '''), reply_markup=builder.as_markup())


async def handle_list(message: Message, speech_repository: Repository):
    speeches = await speech_repository.get_all_speeches()
    await message.answer('\n'.join(timetable.make_entry_string(it) for it in speeches))


def get_router():
    router = Router()
    router.message(CommandStart())(handle_start)
    router.message(Command('list'))(handle_list)
    router.message(Command('configure'))(EditIntentionScene.as_handler())
    logging.getLogger(__name__).info('General handlers registered')
    return router
