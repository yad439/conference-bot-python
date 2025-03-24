import datetime

import pytest

from dto import SpeechDto, TimeSlotDto
from view import timetable


@pytest.fixture
def time_slot():
    return TimeSlotDto(None, datetime.date(2025, 6, 15), datetime.time(9), datetime.time(10))


@pytest.fixture
def speech(time_slot: TimeSlotDto):
    return SpeechDto(None, 'A title', 'A Speaker', time_slot, 'a location')


def test_make_entry_string_default(speech: SpeechDto):
    result = timetable.make_entry_string(speech)
    assert '9:00' in result
    assert '10:00' in result
    assert 'A title' in result
    assert 'A Speaker' in result


def test_make_entry_string_with_location(speech: SpeechDto):
    result = timetable.make_entry_string(
        speech, format_type=timetable.EntryFormat.WITH_PLACE)
    assert '9:00' in result
    assert '10:00' in result
    assert 'A title' in result
    assert 'A Speaker' in result
    assert 'a location' in result


def test_make_entry_string_location_only(speech: SpeechDto):
    result = timetable.make_entry_string(
        speech, format_type=timetable.EntryFormat.PLACE_ONLY)
    assert 'A title' in result
    assert 'A Speaker' in result
    assert 'a location' in result
