import asyncio
import itertools
import operator
from collections.abc import Iterable

from aiogram import Bot

from data.repository import SelectionRepository
from dto import TimeSlotDto
from view import notifications


async def notify_schedule_change(bot: Bot, selection_repository: SelectionRepository,
                                 changed_slots: Iterable[TimeSlotDto]):
    slot_mapping = {slot.id: slot for slot in changed_slots if slot.id is not None}
    selections = await selection_repository.get_user_ids_that_selected(slot_mapping.keys())
    grouped = itertools.groupby(selections, operator.itemgetter(0))
    for i, (user, selection) in enumerate(grouped, 1):
        message = notifications.render_changed(slot_mapping[slot_id] for _, slot_id in selection)
        await bot.send_message(user, **message.as_kwargs())
        if not i % 24:
            await asyncio.sleep(1)
