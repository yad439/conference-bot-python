import datetime
import typing
from collections.abc import Iterable
from enum import Enum, auto

from aiogram.utils.formatting import Bold, Italic, Text, Underline, as_key_value, as_list, as_marked_section
from babel import dates

from dto import SpeechDto, TimeSlotDto
from utility import as_list_section


class EntryFormat(Enum):
    DEFAULT = auto()
    WITH_PLACE = auto()
    PLACE_ONLY = auto()


def _format_time(speech: SpeechDto):
    return f'{speech.time_slot.start_time:%H:%M} - {speech.time_slot.end_time:%H:%M}'


def make_entry_string(speech: SpeechDto, format_type: EntryFormat = EntryFormat.DEFAULT):  # NOSONAR
    match format_type:
        case EntryFormat.DEFAULT:
            return as_key_value(_format_time(speech), Text(speech.title, ' (', Italic(speech.speaker), ')'))
        case EntryFormat.WITH_PLACE:
            return as_key_value(Text(_format_time(speech), ' ', Underline(f'{speech.location}')),
                                Text(speech.title, ' (', Italic(speech.speaker), ')'))
        case EntryFormat.PLACE_ONLY:
            return as_key_value(Underline(speech.location), Text(speech.title, ' (', Italic(speech.speaker), ')'))
    typing.assert_never(format_type)


def make_date_string(date: datetime.date):
    return dates.format_date(date, 'E, dd.MM', locale='ru').capitalize()


def make_date_string_underline(date: datetime.date):
    return Text(dates.format_date(date, 'E, ', locale='ru').capitalize(), Underline(f'{date:%d.%m}'))


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
            header = Text('📆', dates.format_date(date, 'E, dd.MM:', locale='ru').capitalize())
        else:
            header = Text('📆', f'{date:%d.%m}:')
        body: list[Text | str] = []
        for location, speeches in locations:
            body.extend((
                as_marked_section(Text('🏫', location),
                                  *(make_entry_string(speech) for speech in speeches)),
                ''
            ))
        output.append(as_list_section(header, *body))
    return as_list(*output)


def render_personal(table: Iterable[tuple[datetime.date, Iterable[SpeechDto]]]):
    return (as_marked_section(
        Text('🗓️', dates.format_date(date, 'E, dd.MM:\n', locale='ru').capitalize()),
        *(make_entry_string(speech, EntryFormat.WITH_PLACE) for speech in speeches)
    )
        for date, speeches in table)
