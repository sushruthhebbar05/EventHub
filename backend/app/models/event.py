from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.base import TimestampMixin
from app.models.constants import EventStatus, in_list


class Venue(Base, TimestampMixin):
    __tablename__ = "venues"
    __table_args__ = (CheckConstraint("capacity > 0", name="ck_venues_capacity"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(150))
    city: Mapped[str] = mapped_column(String(80), index=True)
    address: Mapped[str] = mapped_column(String(255))
    capacity: Mapped[int]


class Event(Base, TimestampMixin):
    __tablename__ = "events"
    __table_args__ = (
        CheckConstraint(
            in_list("status", [EventStatus.PENDING, EventStatus.APPROVED, EventStatus.REJECTED, EventStatus.CANCELLED]),
            name="ck_events_status",
        ),
        Index("ix_events_status_starts_at", "status", "starts_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    organiser_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    venue_id: Mapped[int] = mapped_column(ForeignKey("venues.id"), index=True)
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default="", server_default="")
    category: Mapped[str] = mapped_column(String(50), index=True)
    image_url: Mapped[str | None] = mapped_column(String(500))
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    status: Mapped[str] = mapped_column(String(20), default=EventStatus.PENDING, server_default=EventStatus.PENDING)

    venue: Mapped[Venue] = relationship(lazy="joined")
    organiser = relationship("User", lazy="select")
