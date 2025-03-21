import datetime
import itertools
from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from view import timetable

from data.repository import Repository


async def handle_personal_view(message: Message, repository: Repository):
    user = message.from_user
    assert user is not None
    text = message.text
    assert text is not None
    match text:
        case '/personal':
            date = None
        case '/today':
            date = datetime.date.today()
        case '/tomorrow':
            date = datetime.date.today() + datetime.timedelta(days=1)
        case _:
            raise ValueError('Unknown command')
    speeches = await repository.get_selected_speeches(user.id, date)
    if not speeches:
        await message.answer('Вы не выбрали ни одной записи')
        return
    days = itertools.groupby(speeches, lambda x: x.time_slot.date)
    await message.answer(timetable.render_personal(days))


def get_router():
    router = Router()
    router.message(Command('personal', 'today', 'tomorrow'))(
        handle_personal_view)
    return router
