import logging
import textwrap
from aiogram import Router
from aiogram.filters import Command, CommandStart
from aiogram.types import Message
from aiogram.utils import keyboard

from database.repository import SpeechRepository


async def handle_start(message: Message):
    builder = keyboard.ReplyKeyboardBuilder()
    builder.button(text='/list')
    builder.button(text='/configure')
    await message.answer(textwrap.dedent('''
    Это бот, предоставляющий информацию о мероприятиях. Команды:
    /list - список всех мероприятий
    /configure - настройка персональной программы
        '''), reply_markup=builder.as_markup())


async def handle_list(message: Message, speech_repository: SpeechRepository):
    speeches = await speech_repository.get_all()
    format_string = '{it.time_slot.date} {it.time_slot.start_time.strftime("%H:%M")}-{it.time_slot.end_time.strftime("%H:%M")}: {it.title} ({it.speaker})'
    await message.answer('\n'.join(format_string.format(it=it) for it in speeches))


def get_router():
    router = Router()
    router.message(CommandStart())(handle_start)
    router.message(Command('list'))(handle_list)
    logging.getLogger(__name__).info('General handlers registered')
    return router
