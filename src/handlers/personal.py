import datetime
from io import StringIO
import itertools
from aiogram.fsm.scene import Scene, SceneRegistry, on
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, ReplyKeyboardRemove
from aiogram.utils.keyboard import ReplyKeyboardBuilder
from aiogram import F, Router
import logging

from data.repository import Repository
from dto import SpeechDto
from view import timetable


class Intention:
    ALL = 'Все'
    DAY = 'День'
    SINGLE = 'Одну запись'


NOTHING_OPTION = 'Ничего'


def init(router: Router):
    registry = SceneRegistry(router)
    registry.add(EditIntentionScene, SelectDayScene,
                 SelectSingleScene, EditingScene)


class EditIntentionScene(Scene, state='editIntention'):
    @on.message.enter()
    async def on_enter(self, message: Message):
        keyboard = ReplyKeyboardBuilder().button(text=Intention.ALL).button(
            text=Intention.DAY).button(text=Intention.SINGLE)
        await message.answer('Какие записи вы хотите отредактировать?', reply_markup=keyboard.as_markup())

    @on.message(F.text)
    async def on_message(self, message: Message, repository: Repository):
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
    @on.message.enter()
    async def on_enter(self, message: Message, state: FSMContext, repository: Repository):
        days = await repository.get_all_dates()
        days.sort()
        day_strings = timetable.make_date_strings(days)
        keyboard = ReplyKeyboardBuilder()
        for i in range(len(days)):
            keyboard.button(text=str(i+1))
        answer = 'Возможные варианты:\n'+'\n'.join(day_strings)
        await state.update_data(days=days)
        await message.answer(answer, reply_markup=keyboard.as_markup())

    @on.message(F.text)
    async def on_message(self, message: Message, state: FSMContext, repository: Repository):
        try:
            text = message.text
            assert text is not None
            value = int(text)
            days: list[datetime.date] | None = await state.get_value('days')
            assert days is not None
            date: datetime.date = days[value-1]
            slots = await repository.get_slot_ids_on_day(date)
            await self.wizard.goto(EditingScene, slots=slots)
        except (ValueError, IndexError):
            await message.answer('Выберете из доступных дней')


class SelectSingleScene(Scene, state='selectSingle'):
    @on.message.enter()
    async def on_enter(self, message: Message, state: FSMContext, repository: Repository):
        slots = await repository.get_all_slots()
        slots.sort(key=lambda slot: slot.date)
        dates = sorted({slot.date for slot in slots})
        date_strings = timetable.make_date_strings(dates)
        slot_mapping: list[int] = []
        result = StringIO('Выберете номер слота:\n')
        for (_, day_slots), header in zip(itertools.groupby(slots, key=lambda slot: slot.date), date_strings):
            result.write(header)
            result.write(':\n')
            sorted_slots = sorted(day_slots, key=lambda x: x.start_time)
            for slot in sorted_slots:
                assert slot.id is not None
                result.write(
                    f'{len(slot_mapping)}: {timetable.make_slot_string(slot)}\n')
                slot_mapping.append(slot.id)
        await state.update_data(slot_mapping=slot_mapping)
        await message.answer(result.getvalue())

    @on.message(F.text)
    async def on_message(self, message: Message, state: FSMContext, repository: Repository):
        slot_mapping: list[int] | None = await state.get_value('slot_mapping')
        assert slot_mapping is not None
        try:
            text = message.text
            assert text is not None
            value = int(text)
            time_slot_id = slot_mapping[value]
            await self.wizard.goto(EditingScene, slots=[time_slot_id])
        except (ValueError, IndexError):
            await message.answer('Выберете из доступных вариантов')


class EditingScene(Scene, state='editing'):
    _logger = logging.getLogger(__name__)

    @on.message.enter()
    async def on_enter(self, message: Message, state: FSMContext, repository: Repository, slots: list[int]):
        if not slots:
            await message.answer('Готово', reply_markup=ReplyKeyboardRemove())
            await self.wizard.exit()
            return
        slot, options = await repository.get_in_time_slot(slots[-1])
        slot_string = timetable.make_slot_string(slot, with_day=True)
        answer = slot_string+'\n' + 'Возможные варианты:\n' + \
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
        await repository.save_selection(user.id, slots[-1], None)
        slots.pop()
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
        self._logger.debug(
            'Selected location "%s" for slot %d', location, slots[-1])
        for option in options:
            if location == option.location:
                selection = option.id
                assert selection is not None
                break
        else:
            await message.answer('Такой локации нет, повторите, пожалуйста')
            return
        user = message.from_user
        assert user is not None
        await repository.save_selection(user.id, slots[-1], selection)
        slots.pop()
        await self.wizard.retake(slots=slots)

    @on.message()
    async def on_unknown(self, message: Message):
        await message.answer('Выберете значение из списка')
