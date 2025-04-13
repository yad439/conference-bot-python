import datetime

from sqlalchemy import BigInteger, ForeignKey
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

# pylint: disable=too-few-public-methods,unsubscriptable-object


class Base(DeclarativeBase):
    pass


class TimeSlot(Base):
    __tablename__ = 'time_slots'
    id: Mapped[int] = mapped_column(primary_key=True)
    date: Mapped[datetime.date] = mapped_column()
    start_time: Mapped[datetime.time] = mapped_column()
    end_time: Mapped[datetime.time] = mapped_column()


class Speech(Base):
    __tablename__ = 'speeches'
    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(unique=True)
    speaker: Mapped[str] = mapped_column()
    time_slot_id: Mapped[int] = mapped_column(ForeignKey('time_slots.id'))
    time_slot: Mapped['TimeSlot'] = relationship()
    location: Mapped[str] = mapped_column()


class Selection(Base):
    __tablename__ = 'selections'
    attendee: Mapped[int] = mapped_column(BigInteger(), primary_key=True)
    time_slot_id: Mapped[int] = mapped_column(
        ForeignKey('time_slots.id'), primary_key=True)
    speech_id: Mapped[int] = mapped_column(ForeignKey('speeches.id'))
    speech: Mapped['Speech'] = relationship()


class Settings(Base):
    __tablename__ = 'settings'
    user_id: Mapped[int] = mapped_column(primary_key=True)
    notifications_enabled: Mapped[bool] = mapped_column(nullable=True)
