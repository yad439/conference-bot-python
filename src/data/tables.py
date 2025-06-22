import datetime

from sqlalchemy import BigInteger, ForeignKey, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

# pylint: disable=too-few-public-methods,unsubscriptable-object


class Base(DeclarativeBase):
    pass


class TimeSlot(Base):
    __tablename__ = 'time_slots'
    id: Mapped[int] = mapped_column(primary_key=True)  # noqa: A003
    date: Mapped[datetime.date] = mapped_column(nullable=False)
    start_time: Mapped[datetime.time] = mapped_column(nullable=False)
    end_time: Mapped[datetime.time] = mapped_column(nullable=False)

    __table_args__ = (
        UniqueConstraint('date', 'start_time', 'end_time'),
    )


class Speech(Base):
    __tablename__ = 'speeches'
    id: Mapped[int] = mapped_column(primary_key=True)  # noqa: A003
    title: Mapped[str] = mapped_column(nullable=False)
    speaker: Mapped[str] = mapped_column(nullable=False)
    time_slot_id: Mapped[int] = mapped_column(ForeignKey('time_slots.id'))
    time_slot: Mapped['TimeSlot'] = relationship()
    location: Mapped[str] = mapped_column(nullable=False)

    __table_args__ = (
        UniqueConstraint('time_slot_id', 'location'),
    )


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
    username: Mapped[str | None]
    notifications_enabled: Mapped[bool] = mapped_column(default=True)
    admin: Mapped[bool] = mapped_column(default=False)
