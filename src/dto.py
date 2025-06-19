import datetime
from dataclasses import dataclass


@dataclass(frozen=True)
class TimeSlotDto:
    id: int | None  # noqa: A003
    date: datetime.date
    start_time: datetime.time
    end_time: datetime.time


@dataclass
class SpeechDto:
    id: int | None  # noqa: A003
    title: str
    speaker: str
    time_slot: TimeSlotDto
    location: str


@dataclass
class SelectionDto:
    attendee: int
    speech: SpeechDto
