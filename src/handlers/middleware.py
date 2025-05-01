from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import Router
from aiogram.types import Chat, Message, TelegramObject


def init_middleware(router: Router):
    router.message.middleware(reroute_to_personal)


def reroute_to_personal(handler: Callable[[Message, dict[str, Any]], Awaitable[Any]],
                        event: TelegramObject, data: dict[str, Any]):
    assert isinstance(event, Message)
    if event.chat.type != 'private':
        user = event.from_user
        assert user is not None
        new_chat = Chat(id=user.id, type='private')
        event = event.model_copy(update={'chat': new_chat})
        if 'scenes' in data:
            data['scenes'].event = event
    return handler(event, data)
