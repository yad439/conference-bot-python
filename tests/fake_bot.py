import datetime
import typing
from collections.abc import Mapping
from io import BytesIO
from typing import Any, Self

import pytest
from aiogram import Bot, Router
from aiogram.fsm.context import FSMContext
from aiogram.methods import (
    AnswerCallbackQuery,
    PinChatMessage,
    SendDocument,
    SendMessage,
    TelegramMethod,
    UnpinAllChatMessages,
)
from aiogram.types import (
    CallbackQuery,
    Chat,
    ChatIdUnion,
    Document,
    FSInputFile,
    InlineKeyboardMarkup,
    InputFile,
    MaybeInaccessibleMessageUnion,
    Message,
    User,
)


class StateFake(FSMContext):
    def __init__(self: Self):
        self.data: dict[str, Any] = {}

    async def update_data(self, data: Mapping[str, Any] | None = None, **kwargs: Any):
        if data:
            self.data.update(data)
        self.data.update(kwargs)
        return self.data

    async def get_data(self):
        return self.data

    async def get_value(self, key: str, default: Any | None = None):
        return self.data.get(key, default)

    async def clear(self):
        self.data.clear()


class BotFake:
    def __init__(self, **kwargs: Any) -> None:
        self.router = Router()
        self.sent_messages: list[str] = []
        self.notifications: list[str] = []
        self.messages: list[Message] = []
        self.pending_queries: set[str] = set()
        self._state = StateFake()
        self._files: dict[str, bytes] = {}
        self._id_counter = 0
        self._data = kwargs
        self._data['bot'] = self
        self._data['state'] = self._state
        async def nop(*_: Any): pass  # Do nothing by default
        self._data['schedule_update_callback'] = nop
        self.pinned: dict[ChatIdUnion, list[Message]] = {}

    @property
    def bot(self):
        return typing.cast('Bot', self)

    async def __call__(self, method: TelegramMethod[Any]):  # NOSONAR
        if isinstance(method, SendMessage):
            chat_id = method.chat_id
            assert isinstance(chat_id, int)
            message_id = self._id_counter
            self._id_counter += 1
            keyboard = method.reply_markup if isinstance(method.reply_markup, InlineKeyboardMarkup) else None
            message = Message(message_id=message_id, date=datetime.datetime.now(),  # noqa: DTZ005
                              chat=Chat(id=chat_id, type='private').as_(self.bot), text=method.text,
                              reply_markup=keyboard).as_(self.bot)
            self.messages.append(message)
            self.sent_messages.append(method.text)
            return message
        if isinstance(method, AnswerCallbackQuery):
            text = method.text
            if text:
                self.notifications.append(text)
            self.pending_queries.discard(method.callback_query_id)
            return True
        if isinstance(method, SendDocument):
            chat_id = method.chat_id
            assert isinstance(chat_id, int)
            file = method.document
            if isinstance(file, str):
                file_id = file
            else:
                typing.assert_type(file, InputFile)
                assert isinstance(file, FSInputFile)
                file_id = str(self._id_counter)
                self._id_counter += 1
                filename = str(file.path)
                self._files[file_id] = filename.encode('utf-8')
            document = Document(file_id=file_id, file_unique_id=file_id,
                                file_name=file.filename if isinstance(file, InputFile) else None).as_(self.bot)
            message = Message(message_id=self._id_counter, date=datetime.datetime.now(datetime.UTC),
                              chat=Chat(id=chat_id, type='private'), document=document).as_(self.bot)
            self._id_counter += 1
            self.messages.append(message)
            self.sent_messages.append(method.caption or '')
            return message
        if isinstance(method, PinChatMessage):
            chat_id = method.chat_id
            message = next(msg for msg in self.messages if msg.message_id == method.message_id)
            if chat_id not in self.pinned:
                self.pinned[chat_id] = []
            self.pinned[chat_id].append(message)
            return True
        if isinstance(method, UnpinAllChatMessages):
            chat_id = method.chat_id
            if chat_id in self.pinned:
                del self.pinned[chat_id]
            return True
        pytest.fail(f'Unsupported method: {type(method)}')

    async def download(self, file_id: str):  # NOSONAR
        return BytesIO(self._files[file_id])

    def message(self, text: str, user_id: int = 42, chat_id: int = 42, username: str | None = 'testUser',
                file: tuple[str, bytes] | None = None):
        chat = Chat(id=chat_id, type='private') if chat_id == user_id else Chat(id=chat_id, type='group')
        user = User(id=user_id, is_bot=False, first_name='Test', username=username)
        if file is not None:
            file_id = str(self._id_counter)
            self._id_counter += 1
            document = Document(file_id=file_id, file_unique_id=file_id, file_name=file[0])
            self._files[file_id] = file[1]
        else:
            document = None
        message = Message(message_id=self._id_counter, date=datetime.datetime.now(datetime.UTC),
                          chat=chat, text=text, from_user=user, document=document).as_(self.bot)
        self._id_counter += 1
        return self.router.propagate_event('message', message, **self._data)

    def query(self, source_message: MaybeInaccessibleMessageUnion, text: str, user_id: int = 42):
        user = User(id=user_id, is_bot=False, first_name='Test', username='testUser')
        query_id = str(self._id_counter)
        self._id_counter += 1
        query = CallbackQuery(id=query_id, from_user=user, chat_instance='123',
                              message=source_message, data=text).as_(self.bot)
        self.pending_queries.add(query_id)
        return self.router.propagate_event('callback_query', query, **self._data)
