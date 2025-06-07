import datetime
import itertools
import logging

from aiogram import Bot
from apscheduler.schedulers.base import BaseScheduler  # type: ignore

from data.repository import Repository
from view import notifications


async def configure_events(scheduler: BaseScheduler, repository: Repository, bot: Bot, minutes_before_start: int):
    slots = await repository.get_all_slots()
    for date, day_slots in itertools.groupby(slots, key=lambda slot: slot.date):
        prev_slot = next(day_slots)
        prev_id = prev_slot.id
        assert prev_id is not None
        execution_time = (datetime.datetime.combine(date, prev_slot.start_time)
                          - datetime.timedelta(minutes=minutes_before_start))
        scheduler.add_job(notify_first, 'date',  # pyright: ignore[reportUnknownMemberType]
                          (bot, repository, prev_id, minutes_before_start), run_date=execution_time)
        for slot in day_slots:  # noqa: B031
            current_id = slot.id
            assert current_id is not None
            execution_time = (datetime.datetime.combine(date, slot.start_time)
                              - datetime.timedelta(minutes=minutes_before_start))
            scheduler.add_job(notify_change_location, 'date',  # pyright: ignore[reportUnknownMemberType]
                              (bot, repository, current_id, prev_id, minutes_before_start), run_date=execution_time)
            prev_id = current_id
    logging.getLogger(__name__).info('Notifications scheduled')


async def notify_first(bot: Bot, repository: Repository,
                       time_slot_id: int, time_to_start: int):
    selections = await repository.get_users_that_selected(time_slot_id)
    logging.getLogger(__name__).info('Notifying %d users about first speech', len(selections))
    for selection in selections:
        await bot.send_message(selection.attendee, notifications.render_starting(selection.speech, time_to_start))


async def notify_change_location(bot: Bot, repository: Repository,
                                 time_slot_id: int, previous_slot_id: int, time_to_start: int):
    selections = await repository.get_changing_users(time_slot_id, previous_slot_id)
    logging.getLogger(__name__).info('Notifying %d users about location change', len(selections))
    for selection in selections:
        await bot.send_message(selection.attendee, notifications.render_starting(selection.speech, time_to_start))
