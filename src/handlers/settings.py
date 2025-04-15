import logging

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

import view
import view.notifications
from data.repository import Repository


async def handle_show_settings(message: Message, repository: Repository):
    user = message.from_user
    assert user is not None
    notifications = await repository.get_notification_setting(user.id)
    if notifications is None:
        notifications = True
    answer = view.notifications.render_settings(notifications)
    await message.answer(answer, reply_markup=_build_settings_keyboard())


async def handle_set_setting(callback: CallbackQuery, repository: Repository):
    logger = logging.getLogger(__name__)
    query = callback.data
    match query:
        case 'set_notifications_on':
            logger.info('User %d enabled notifications', callback.from_user.id)
            await repository.save_notification_setting(callback.from_user.id, True)
            await callback.answer('Уведомления включены')
            enabled = True
        case 'set_notifications_off':
            logger.info('User %d disabled notifications', callback.from_user.id)
            await repository.save_notification_setting(callback.from_user.id, False)
            await callback.answer('Уведомления выключены')
            enabled = False
        case _:
            logger.error('Received unknown settings command %s', query)
            await callback.answer('Неизвестная команда')
            return
    message = callback.message
    if isinstance(message, Message):
        await message.edit_text(view.notifications.render_settings(enabled), reply_markup=_build_settings_keyboard())


def _build_settings_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text='Включить уведомления', callback_data='set_notifications_on'),
        InlineKeyboardButton(text='Выключить уведомления', callback_data='set_notifications_off')]])


def get_router():
    router = Router()
    router.message.register(handle_show_settings, Command('settings'))
    router.callback_query.register(handle_set_setting, F.data.startswith('set_notifications_'))
    logging.getLogger(__name__).debug('Settings router configured')
    return router
