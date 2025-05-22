import datetime
import typing
from typing import Any, Self

from aiogram import Bot, Router
from aiogram.methods import AnswerCallbackQuery, SendMessage, TelegramMethod
from aiogram.types import CallbackQuery, Chat, InlineKeyboardMarkup, MaybeInaccessibleMessageUnion, Message, User


class StateFake:
    def __init__(self: Self):
        self.data: dict[str, Any] = {}

    async def update_data(self, **kwargs: Any):
        self.data.update(kwargs)

    async def get_data(self):
        return self.data

    async def get_value(self, key: str):
        return self.data[key]

    async def clear(self):
        self.data.clear()


class BotFake:
    def __init__(self, **kwargs: Any):
        self.router = Router()
        self.sent_messages: list[str] = []
        self.notifications: list[str] = []
        self.messages: list[Message] = []
        self.pending_queries: set[str] = set()
        self._state = StateFake()
        self._message_counter = 0
        self._data = kwargs
        self._data['bot'] = self
        self._data['state'] = self._state

    @property
    def bot(self):
        return typing.cast(Bot, self)

    async def __call__(self, method: TelegramMethod[Any]):
        if isinstance(method, SendMessage):
            chat_id = method.chat_id
            assert isinstance(chat_id, int)
            message_id = self._message_counter
            self._message_counter += 1
            keyboard = method.reply_markup if isinstance(method.reply_markup, InlineKeyboardMarkup) else None
            message = Message(message_id=message_id, date=datetime.datetime.now(),
                              chat=Chat(id=chat_id, type='private'), text=method.text,
                              reply_markup=keyboard).as_(self.bot)
            self.messages.append(message)
            self.sent_messages.append(method.text)
            return message
        elif isinstance(method, AnswerCallbackQuery):
            text = method.text
            if text:
                self.notifications.append(text)
            self.pending_queries.discard(method.callback_query_id)
            return True
        assert False

    def message(self, text: str, user_id: int = 42, chat_id: int = 42, username: str | None = 'testUser'):
        chat = Chat(id=chat_id, type='private') if chat_id == user_id else Chat(id=chat_id, type='group')
        user = User(id=user_id, is_bot=False, first_name='Test', username=username)
        message = Message(message_id=self._message_counter, date=datetime.datetime.now(),
                          chat=chat, text=text, from_user=user).as_(self.bot)
        self._message_counter += 1
        return self.router.propagate_event('message', message, **self._data)

    def query(self, source_message: MaybeInaccessibleMessageUnion, text: str, user_id: int = 42):
        user = User(id=user_id, is_bot=False, first_name='Test', username='testUser')
        query_id = str(self._message_counter)
        self._message_counter += 1
        query = CallbackQuery(id=query_id, from_user=user, chat_instance='123',
                              message=source_message, data=text).as_(self.bot)
        self.pending_queries.add(query_id)
        return self.router.propagate_event('callback_query', query, **self._data)
