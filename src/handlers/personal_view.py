import itertools
from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from view import timetable

from data.repository import Repository


async def handle_personal_view(message: Message, repository: Repository):
    user = message.from_user
    assert user is not None
    speeches = await repository.get_selected_speeches(user.id)
    if not speeches:
        await message.answer('Вы не выбрали ни одной записи')
        return
    days = itertools.groupby(speeches, lambda x: x.time_slot.date)
    await message.answer(timetable.render_personal(days))


def get_router():
    router = Router()
    router.message(Command('personal'))(handle_personal_view)
    return router
