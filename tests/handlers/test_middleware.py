import datetime
from types import SimpleNamespace

import pytest
from aiogram import Router
from aiogram.types import Chat, Message, User

from handlers import middleware


@pytest.mark.asyncio
async def test_reroute_to_personal():
    message = Message(message_id=1, date=datetime.datetime(1, 1, 1),  # noqa: DTZ001
                      chat=Chat(id=10, type='group'),
                      from_user=User(id=1, is_bot=False, first_name='Test', last_name='User', username='testuser'))
    router = Router()
    scenes = SimpleNamespace()

    async def mock_handler(message: Message):  # noqa: RUF029 NOSONAR
        assert message.chat.type == 'private'
        assert message.chat.id == 1

    router.message.register(mock_handler)

    middleware.init_middleware(router)
    await router.propagate_event('message', message, scenes=scenes)
    assert scenes.event.chat.type == 'private'
    assert scenes.event.chat.id == 1
