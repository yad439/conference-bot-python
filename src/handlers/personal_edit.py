import itertools
import logging
from collections.abc import Iterable, Sequence
from io import StringIO
from typing import TYPE_CHECKING, Any

from aiogram import F, Router
from aiogram.filters import Command, and_f
from aiogram.fsm.context import FSMContext
from aiogram.fsm.scene import Scene, SceneRegistry, on
from aiogram.types import CallbackQuery, Message, ReplyKeyboardRemove, User
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder

from data.repository import SelectionRepository, SpeechRepository
from view import timetable

if TYPE_CHECKING:
    import datetime

    from dto import SpeechDto


class Intention:  # pylint: disable=too-few-public-methods
    ALL = 'Все'
    DAY = 'День'
    SINGLE = 'Одну запись'


NOTHING_OPTION = 'Ничего'


def init(router: Router):
    registry = SceneRegistry(router)
    registry.add(EditIntentionScene, SelectDayScene, SelectSingleScene, EditingScene)
    router.message.register(EditIntentionScene.as_handler(), Command('configure'))
    router.callback_query.register(handle_selection_query, and_f(F.data.startswith('select#'), _scene_filter))


async def _scene_filter(*_: Any, **kwargs: Any):
    state: FSMContext = kwargs['state']
    current_state = await state.get_state()
    return current_state != 'editing'


def _format_user(user: User | None):
    if user is None:
        return 'Unknown'
    return f'{user.first_name} {user.last_name} ({user.id})'


class EditIntentionScene(Scene, state='editIntention'):
    _logger = logging.getLogger(__name__)

    @on.message.enter()
    async def on_enter(self, message: Message):
        self._logger.debug('User %s started editing personal schedule', _format_user(message.from_user))
        keyboard = ReplyKeyboardBuilder().button(text=Intention.ALL).button(
            text=Intention.DAY).button(text=Intention.SINGLE)
        await message.answer('Какие записи вы хотите отредактировать?', reply_markup=keyboard.as_markup())

    @on.message(F.text)
    async def on_message(self, message: Message, speech_repository: SpeechRepository):
        self._logger.debug('User %s selected to edit %s', _format_user(message.from_user), message.text)
        match message.text:
            case Intention.ALL:
                slots = await speech_repository.get_all_slot_ids()
                await self.wizard.goto(EditingScene, slots=slots)
            case Intention.DAY:
                await self.wizard.goto(SelectDayScene)
            case Intention.SINGLE:
                await self.wizard.goto(SelectSingleScene)
            case _:
                await message.answer('Выберете, что хотите отредактировать')


class SelectDayScene(Scene, state='selectDay'):
    _logger = logging.getLogger(__name__)

    @on.message.enter()
    async def on_enter(self, message: Message, state: FSMContext, speech_repository: SpeechRepository):
        self._logger.debug('User %s started selecting day', _format_user(message.from_user))
        days = await speech_repository.get_all_dates()
        keyboard = ReplyKeyboardBuilder()
        for day in days:
            keyboard.button(text=day.strftime('%d.%m'))
        answer = 'Возможные варианты:\n' + '\n'.join(map(timetable.make_date_string, days))
        await state.update_data(days={day.strftime('%d.%m'): day for day in days}
                                | {str(i + 1): day for i, day in enumerate(days)})
        await message.answer(answer, reply_markup=keyboard.as_markup())

    @on.message(F.text)
    async def on_message(self, message: Message, state: FSMContext, speech_repository: SpeechRepository):
        self._logger.debug('User %s selected day %s', _format_user(message.from_user), message.text)
        text = message.text
        assert text is not None
        days: dict[str, datetime.date] | None = await state.get_value('days')
        assert days is not None
        if text not in days:
            self._logger.warning('User %s selected invalid day %s', _format_user(message.from_user), message.text)
            await message.answer('Выберете из доступных дней')
            return
        date = days[text]
        slots = await speech_repository.get_slot_ids_on_day(date)
        await self.wizard.goto(EditingScene, slots=slots)


class SelectSingleScene(Scene, state='selectSingle'):
    _logger = logging.getLogger(__name__)

    @on.message.enter()
    async def on_enter(self, message: Message, state: FSMContext, speech_repository: SpeechRepository):
        self._logger.debug('User %s started selecting single slot', _format_user(message.from_user))
        slots = await speech_repository.get_all_slots()
        slot_mapping: list[int] = []
        result = StringIO()
        result.write('Выберете номер слота:\n')
        for date, day_slots in itertools.groupby(slots, key=lambda slot: slot.date):
            result.write(timetable.make_date_string(date))
            result.write(':\n')
            for slot in day_slots:
                assert slot.id is not None
                result.write(f'{len(slot_mapping)}: {timetable.make_slot_string(slot)}\n')
                slot_mapping.append(slot.id)
        await state.update_data(slot_mapping=slot_mapping)
        await message.answer(result.getvalue(), reply_markup=ReplyKeyboardRemove())

    @on.message(F.text)
    async def on_message(self, message: Message, state: FSMContext):
        self._logger.debug('User %s selected single slot %s', _format_user(message.from_user), message.text)
        slot_mapping: list[int] | None = await state.get_value('slot_mapping')
        assert slot_mapping is not None
        try:
            text = message.text
            assert text is not None
            value = int(text)
            if value < 0:
                await message.answer('Выберете из доступных вариантов')
                return
            time_slot_id = slot_mapping[value]
            await self.wizard.goto(EditingScene, slots=(time_slot_id,))
        except (ValueError, IndexError):
            self._logger.warning('User %s selected invalid slot %s', _format_user(message.from_user), message.text)
            await message.answer('Выберете из доступных вариантов')


class EditingScene(Scene, state='editing'):
    _logger = logging.getLogger(__name__)

    @on.message.enter()
    async def on_enter(self, message: Message, state: FSMContext, speech_repository: SpeechRepository,
                       slots: Sequence[int]):
        self._logger.debug('User %s editing schedule: slots remaining %s', _format_user(message.from_user), slots)
        if not slots:
            await message.answer('Готово', reply_markup=ReplyKeyboardRemove())
            await self.wizard.exit()
            return
        slot, options = await speech_repository.get_in_time_slot(slots[0])
        slot_string = timetable.make_slot_string(slot, with_day=True)
        answer = 'Возможные варианты:\n' + \
            '\n'.join(timetable.make_entry_string(it, timetable.EntryFormat.PLACE_ONLY)
                      for it in options)
        reply_keyboard = ReplyKeyboardBuilder()
        for option in options:
            reply_keyboard.button(text=option.location)
        reply_keyboard.button(text=NOTHING_OPTION).button(text='Отмена')
        inline_keyboard = InlineKeyboardBuilder()
        for option in options:
            inline_keyboard.button(text=option.location, callback_data=f'select#{slot.id}#{option.id}')
        inline_keyboard.button(text=NOTHING_OPTION, callback_data=f'select#{slot.id}#-1')
        await state.update_data(slots=slots, options=options)
        await message.answer(slot_string, reply_markup=reply_keyboard.as_markup())
        await message.answer(answer, reply_markup=inline_keyboard.as_markup())

    @on.callback_query.enter()
    async def on_query_enter(self, callback: CallbackQuery, state: FSMContext, speech_repository: SpeechRepository,
                             slots: Sequence[int]):
        self._logger.debug('User %s editing schedule: slots remaining %s', _format_user(callback.from_user), slots)
        message = callback.message
        if isinstance(message, Message):
            await self.on_enter(message, state, speech_repository, slots)
            await callback.answer()
        else:
            self._logger.warning('User %s tried to edit schedule, but message is not a Message, but %s',
                                 _format_user(callback.from_user), type(message))
            await callback.answer('Что-то пошло не так')
            await self.wizard.exit()

    @on.message(F.text == NOTHING_OPTION)
    async def on_nothing(self, message: Message, state: FSMContext, selection_repository: SelectionRepository):
        slots: Sequence[int] | None = await state.get_value('slots')
        assert slots is not None
        user = message.from_user
        assert user is not None
        self._logger.debug('User %s selected nothing for slot %d', _format_user(user), slots[0])
        await selection_repository.save_selection(user.id, slots[0], None)
        await self.wizard.retake(slots=slots[1:])

    @on.message(F.text)
    async def on_message(self, message: Message, state: FSMContext, selection_repository: SelectionRepository):
        location = message.text
        if location == NOTHING_OPTION:
            await self.on_nothing(message, state, selection_repository)
            return
        if location == 'Отмена':
            self._logger.debug('User %s cancelled editing', _format_user(message.from_user))
            await message.answer('Готово', reply_markup=ReplyKeyboardRemove())
            await self.wizard.exit()
            return
        selection = None
        data = await state.get_data()
        options: Iterable[SpeechDto] = data['options']
        slots: Sequence[int] = data['slots']
        user = message.from_user
        assert user is not None
        self._logger.debug('User %s selected location "%s" for slot %d', _format_user(user), location, slots[0])
        for option in options:
            if location == option.location:
                selection = option.id
                assert selection is not None
                break
        else:
            await message.answer('Такой локации нет, повторите, пожалуйста')
            return
        await selection_repository.save_selection(user.id, slots[0], selection)
        await self.wizard.retake(slots=slots[1:])

    @on.callback_query(F.data.startswith('select#'))
    async def on_query(self, callback: CallbackQuery, state: FSMContext, selection_repository: SelectionRepository):
        self._logger.debug('User %s selected location from inline keyboard', _format_user(callback.from_user))
        slot = await handle_selection_query(callback, selection_repository)
        slots: Sequence[int] | None = await state.get_value('slots')
        assert slots is not None
        if slots[0] == slot:
            await self.wizard.retake(slots=slots[1:])

    @staticmethod
    @on.message()
    async def on_unknown(message: Message):
        await message.answer('Выберете значение из списка')


async def handle_selection_query(callback: CallbackQuery, selection_repository: SelectionRepository):
    query = callback.data
    assert query is not None
    data = query.split('#')
    slot = int(data[1])
    selection: int | None = int(data[2])
    if selection == -1:
        selection = None
    user = callback.from_user
    assert user is not None
    logging.getLogger(__name__).debug('User %s selected speech %s for slot %d', _format_user(user), selection, slot)
    await selection_repository.save_selection(user.id, slot, selection)
    await callback.answer('Сохранено')
    return slot
