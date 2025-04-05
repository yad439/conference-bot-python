import datetime
from dataclasses import dataclass


@dataclass
class TimeSlotDto:
    id: int | None
    date: datetime.date
    start_time: datetime.time
    end_time: datetime.time


@dataclass
class SpeechDto:
    id: int | None
    title: str
    speaker: str
    time_slot: TimeSlotDto
    location: str


@dataclass
class SelectionDto:
    attendee: int
    speech: SpeechDto
