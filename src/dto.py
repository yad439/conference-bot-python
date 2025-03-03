from dataclasses import dataclass
import datetime


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
