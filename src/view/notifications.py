from collections.abc import Iterable

from dto import SpeechDto, TimeSlotDto
from utility import as_list_section
from view import timetable


def render_starting(speech: SpeechDto, time_to_start: int):
    return f'Через {time_to_start} минут начинается доклад "{speech.title}" ({speech.location})'


def render_settings(enabled: bool):
    return f'Текущие настройки:\nУведомления {'включены' if enabled else 'выключены'}'


def render_changed(time_slots: Iterable[TimeSlotDto]):
    slot_strings = (timetable.make_slot_string(slot, bold=False) for slot in time_slots)
    return as_list_section('Поменялось расписание для следующих слотов:', *slot_strings, 'Проверьте ваш выбор')
