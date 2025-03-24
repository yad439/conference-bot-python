import datetime
from collections.abc import Iterable  # pylint: disable=import-error
from enum import Enum, auto
from io import StringIO

from dto import SpeechDto, TimeSlotDto

ENTRY_FORMAT = '{start:%H:%M} - {end:%H:%M}: {title} ({speaker})'
ENTRY_PLACE_FORMAT = '{start:%H:%M} - {end:%H:%M} {location}: {title} ({speaker})'
ENTRY_PLACE_ONLY_FORMAT = '{location}: {title} ({speaker})'


class EntryFormat(Enum):
    DEFAULT = auto()
    WITH_PLACE = auto()
    PLACE_ONLY = auto()


def make_entry_string(speech: SpeechDto, format_type: EntryFormat = EntryFormat.DEFAULT):
    match format_type:
        case EntryFormat.DEFAULT:
            format_string = ENTRY_FORMAT
        case EntryFormat.WITH_PLACE:
            format_string = ENTRY_PLACE_FORMAT
        case EntryFormat.PLACE_ONLY:
            format_string = ENTRY_PLACE_ONLY_FORMAT
    return format_string.format(title=speech.title, speaker=speech.speaker, location=speech.location,
                                start=speech.time_slot.start_time, end=speech.time_slot.end_time)


def make_date_strings(dates: Iterable[datetime.date]):
    return [f'День {i + 1}: {date:%d.%m}' for i, date in enumerate(dates)]


def make_slot_string(slot: TimeSlotDto, with_day: bool = False):
    if with_day:
        return f'{slot.date:%d.%m} {slot.start_time:%H:%M} - {slot.end_time:%H:%M}'
    return f'{slot.start_time:%H:%M} - {slot.end_time:%H:%M}'


def render_timetable(
        table: Iterable[tuple[datetime.date, Iterable[tuple['str', Iterable[SpeechDto]]]]],
        with_day_counter: bool = True):
    output = StringIO()
    for day, (date, locations) in enumerate(table):
        if with_day_counter:
            output.write(f'День {day + 1} ({date:%d.%m}):\n')
        else:
            output.write(f'{date:%d.%m}:\n')
        for location, speeches in locations:
            output.write(f'{location}:\n')
            for speech in speeches:
                output.write(make_entry_string(speech))
                output.write('\n')
            output.write('\n')
    return output.getvalue()


def render_personal(table: Iterable[tuple[datetime.date, Iterable[SpeechDto]]]):
    output = StringIO()
    for date, speeches in table:
        output.write(f'{date:%d.%m}:\n')
        for speech in speeches:
            output.write(make_entry_string(speech, EntryFormat.WITH_PLACE))
            output.write('\n')
    return output.getvalue()
