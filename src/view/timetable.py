import datetime
import typing
from collections.abc import Iterable
from enum import Enum, auto

from aiogram.utils.formatting import Bold, Italic, Text, as_key_value, as_list
from babel import dates

from dto import SpeechDto, TimeSlotDto
from utility import as_list_section


class EntryFormat(Enum):
    DEFAULT = auto()
    WITH_PLACE = auto()
    PLACE_ONLY = auto()


def _format_time(speech: SpeechDto):
    return f'{speech.time_slot.start_time:%H:%M} - {speech.time_slot.end_time:%H:%M}'


def make_entry_string(speech: SpeechDto, format_type: EntryFormat = EntryFormat.DEFAULT):
    match format_type:
        case EntryFormat.DEFAULT:
            return as_key_value(_format_time(speech), Text(speech.title, ' (', Italic(speech.speaker), ')'))
        case EntryFormat.WITH_PLACE:
            return as_key_value(_format_time(speech) + f' {speech.location}',
                                Text(speech.title, ' (', Italic(speech.speaker), ')'))
        case EntryFormat.PLACE_ONLY:
            return as_key_value(speech.location, Text(speech.title, ' (', Italic(speech.speaker), ')'))
        case _:
            typing.assert_never(format_type)


def make_date_string(date: datetime.date):
    return dates.format_date(date, 'E, dd.MM', locale='ru').capitalize()


def make_slot_string(slot: TimeSlotDto, with_day: bool = False, bold: bool = True):
    if with_day:
        text = (dates.format_date(slot.date, 'E, dd.MM', locale='ru').capitalize() +
                f' {slot.start_time:%H:%M} - {slot.end_time:%H:%M}')
    else:
        text = f'{slot.start_time:%H:%M} - {slot.end_time:%H:%M}'
    return Bold(text) if bold else Text(text)


def render_timetable(
        table: Iterable[tuple[datetime.date, Iterable[tuple['str', Iterable[SpeechDto]]]]],
        with_day_counter: bool = True):
    output: list[Text] = []
    for date, locations in table:
        if with_day_counter:
            header = dates.format_date(date, 'E, dd.MM:', locale='ru').capitalize()
        else:
            header = f'{date:%d.%m}:'
        body: list[Text | str] = []
        for location, speeches in locations:
            body.append(as_list_section(location, *(make_entry_string(speech) for speech in speeches)))
            body.append('')
        output.append(as_list_section(header, *body))
    return as_list(*output)


def render_personal(table: Iterable[tuple[datetime.date, Iterable[SpeechDto]]]):
    for date, speeches in table:
        header = dates.format_date(date, 'E, dd.MM:\n', locale='ru').capitalize()
        body = (make_entry_string(speech, EntryFormat.WITH_PLACE) for speech in speeches)
        yield as_list_section(header, *body)
