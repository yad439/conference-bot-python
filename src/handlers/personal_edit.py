import datetime
import itertools
import logging
from io import StringIO

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.scene import Scene, SceneRegistry, on
from aiogram.types import Message, ReplyKeyboardRemove, User
from aiogram.utils.keyboard import ReplyKeyboardBuilder

from data.repository import Repository
from dto import SpeechDto
from view import timetable


class Intention:  # pylint: disable=too-few-public-methods
    ALL = 'Все'
    DAY = 'День'
    SINGLE = 'Одну запись'


NOTHING_OPTION = 'Ничего'


def init(router: Router):
    registry = SceneRegistry(router)
    registry.add(EditIntentionScene, SelectDayScene,
                 SelectSingleScene, EditingScene)
    router.message(Command('configure'))(EditIntentionScene.as_handler())


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
    async def on_message(self, message: Message, repository: Repository):
        self._logger.debug('User %s selected to edit %s', _format_user(message.from_user), message.text)
        match message.text:
            case Intention.ALL:
                slots = await repository.get_all_slot_ids()
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
    async def on_enter(self, message: Message, state: FSMContext, repository: Repository):
        self._logger.debug('User %s started selecting day', _format_user(message.from_user))
        days = await repository.get_all_dates()
        keyboard = ReplyKeyboardBuilder()
        for i in range(len(days)):
            keyboard.button(text=str(i + 1))
        answer = 'Возможные варианты:\n' + '\n'.join(map(timetable.make_date_string, days))
        await state.update_data(days=days)
        await message.answer(answer, reply_markup=keyboard.as_markup())

    @on.message(F.text)
    async def on_message(self, message: Message, state: FSMContext, repository: Repository):
        self._logger.debug('User %s selected day %s', _format_user(message.from_user), message.text)
        try:
            text = message.text
            assert text is not None
            value = int(text)
            if value < 1:
                await message.answer('Выберете из доступных дней')
                return
            days: list[datetime.date] | None = await state.get_value('days')
            assert days is not None
            date: datetime.date = days[value - 1]
            slots = await repository.get_slot_ids_on_day(date)
            await self.wizard.goto(EditingScene, slots=slots)
        except (ValueError, IndexError):
            self._logger.warning('User %s selected invalid day %s', _format_user(message.from_user), message.text)
            await message.answer('Выберете из доступных дней')


class SelectSingleScene(Scene, state='selectSingle'):
    _logger = logging.getLogger(__name__)

    @on.message.enter()
    async def on_enter(self, message: Message, state: FSMContext, repository: Repository):
        self._logger.debug('User %s started selecting single slot', _format_user(message.from_user))
        slots = await repository.get_all_slots()
        slot_mapping: list[int] = []
        result = StringIO('Выберете номер слота:\n')
        for date, day_slots in itertools.groupby(slots, key=lambda slot: slot.date):
            result.write(timetable.make_date_string(date))
            result.write(':\n')
            for slot in day_slots:
                assert slot.id is not None
                result.write(f'{len(slot_mapping)}: {timetable.make_slot_string(slot)}\n')
                slot_mapping.append(slot.id)
        await state.update_data(slot_mapping=slot_mapping)
        await message.answer(result.getvalue())

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
            await self.wizard.goto(EditingScene, slots=[time_slot_id])
        except (ValueError, IndexError):
            self._logger.warning('User %s selected invalid slot %s', _format_user(message.from_user), message.text)
            await message.answer('Выберете из доступных вариантов')


class EditingScene(Scene, state='editing'):
    _logger = logging.getLogger(__name__)

    @on.message.enter()
    async def on_enter(self, message: Message, state: FSMContext, repository: Repository, slots: list[int]):
        self._logger.debug('User %s editing schedule: slots remaining %s', _format_user(message.from_user), slots)
        if not slots:
            await message.answer('Готово', reply_markup=ReplyKeyboardRemove())
            await self.wizard.exit()
            return
        slot, options = await repository.get_in_time_slot(slots[0])
        slot_string = timetable.make_slot_string(slot, with_day=True)
        answer = slot_string + '\n' + 'Возможные варианты:\n' + \
            '\n'.join(timetable.make_entry_string(it, timetable.EntryFormat.PLACE_ONLY)
                      for it in options)
        keyboard = ReplyKeyboardBuilder()
        for option in options:
            keyboard.button(text=option.location)
        keyboard.button(text=NOTHING_OPTION)
        await state.update_data(slots=slots, options=options)
        await message.answer(answer, reply_markup=keyboard.as_markup())

    @on.message(F.text == NOTHING_OPTION)
    async def on_nothing(self, message: Message, state: FSMContext, repository: Repository):
        slots: list[int] | None = await state.get_value('slots')
        assert slots is not None
        user = message.from_user
        assert user is not None
        self._logger.debug('User %s selected nothing for slot %d', user, slots[0])
        await repository.save_selection(user.id, slots[0], None)
        slots.pop(0)
        await self.wizard.retake(slots=slots)

    @on.message(F.text)
    async def on_message(self, message: Message, state: FSMContext, repository: Repository):
        location = message.text
        if location == NOTHING_OPTION:
            await self.on_nothing(message, state, repository)
            return
        selection = None
        data = await state.get_data()
        options: list[SpeechDto] = data['options']
        slots: list[int] = data['slots']
        user = message.from_user
        assert user is not None
        self._logger.debug('User %s selected location "%s" for slot %d', user, location, slots[0])
        for option in options:
            if location == option.location:
                selection = option.id
                assert selection is not None
                break
        else:
            await message.answer('Такой локации нет, повторите, пожалуйста')
            return
        await repository.save_selection(user.id, slots[0], selection)
        slots.pop(0)
        await self.wizard.retake(slots=slots)

    @on.message()
    async def on_unknown(self, message: Message):
        await message.answer('Выберете значение из списка')
