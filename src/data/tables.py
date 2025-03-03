import datetime
from sqlalchemy import BigInteger, ForeignKey, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


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
    __table_args__ = (UniqueConstraint('attendee', 'time_slot_id'),)
    id: Mapped[int] = mapped_column(primary_key=True)
    attendee: Mapped[int] = mapped_column(BigInteger())
    time_slot_id = mapped_column(ForeignKey('time_slots.id'))
    speech_id: Mapped[int] = mapped_column(ForeignKey('speeches.id'))
    speech: Mapped['Speech'] = relationship()
