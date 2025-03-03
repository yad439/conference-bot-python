import datetime
from collections.abc import Iterable
from enum import Enum, auto
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
            format = ENTRY_FORMAT
        case EntryFormat.WITH_PLACE:
            format = ENTRY_PLACE_FORMAT
        case EntryFormat.PLACE_ONLY:
            format = ENTRY_PLACE_ONLY_FORMAT
    return format.format(title=speech.title, speaker=speech.speaker, location=speech.location, start=speech.time_slot.start_time, end=speech.time_slot.end_time)


def make_date_strings(dates: Iterable[datetime.date]):
    return [f'День {i+1}: {date:%d.%m}' for i, date in enumerate(dates)]


def make_slot_string(slot: TimeSlotDto, with_day: bool = False):
    if with_day:
        return f'{slot.date:%d.%m} {slot.start_time:%H:%M} - {slot.end_time:%H:%M}'
    else:
        return f'{slot.start_time:%H:%M} - {slot.end_time:%H:%M}'
