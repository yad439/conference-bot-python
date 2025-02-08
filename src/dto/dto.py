from dataclasses import dataclass
import datetime


@dataclass
class TimeSlotDto:
    date: datetime.date
    start_time: datetime.time
    end_time: datetime.time


@dataclass
class SpeechDto:
    title: str
    speaker: str
    time_slot: TimeSlotDto
    location: str
