import logging
from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message, TelegramObject

from data.repository import Repository


async def check_rights_middleware(handler: Callable[[Message, dict[str, Any]], Awaitable[Any]],
                                  event: TelegramObject, data: dict[str, Any]):
    repository: Repository = data['repository']
    assert isinstance(event, Message)
    user = event.from_user
    assert user is not None
    admin = await repository.is_admin(user.id)
    if admin:
        return await handler(event, data)
    return None


async def set_admin_handler(message: Message, repository: Repository):
    logger = logging.getLogger(__name__)
    text = message.text
    logger.debug('Processing admin command: %s', text)
    assert text is not None

    command = text.split(' ')
    if len(command) != 2:
        await message.answer('Неверный формат команды. Используйте /admin или /unadmin <ID/username>')
        logger.warning('Invalid command format: %s', text)
        return

    make_admin = command[0] == '/admin'
    action_msg = "Пользователь {} стал администратором" if make_admin else "Пользователь {} больше не администратор"
    action_log = "%s became admin" if make_admin else "%s is no longer admin"

    identifier = command[1]
    if identifier.isdecimal():
        user_id = int(identifier)
        await repository.set_admin(user_id, make_admin)
        await message.answer(action_msg.format(user_id))
        logger.info(action_log, user_id)
    else:
        success = await repository.set_admin_by_username(identifier, make_admin)
        if success:
            await message.answer(action_msg.format(identifier))
            logger.info(action_log, identifier)
        else:
            await message.answer(f'Пользователь {identifier} не найден')
            logger.info('User %s not found for admin privileges', identifier)


def get_router():
    router = Router()
    router.message.register(set_admin_handler, Command('admin'))
    router.message.register(set_admin_handler, Command('unadmin'))
    router.message.middleware(check_rights_middleware)
    return router
