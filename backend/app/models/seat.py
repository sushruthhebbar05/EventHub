from datetime import datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Numeric, String, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.base import TimestampMixin
from app.models.constants import HoldStatus, SeatStatus, in_list


class Seat(Base, TimestampMixin):
    """One physical seat *for one event*. Its status is the single source of truth for availability."""

    __tablename__ = "seats"
    __table_args__ = (
        UniqueConstraint("event_id", "section", "row_label", "number", name="uq_seat_position"),
        CheckConstraint(in_list("status", [SeatStatus.AVAILABLE, SeatStatus.HELD, SeatStatus.BOOKED]), name="ck_seats_status"),
        CheckConstraint("price >= 0", name="ck_seats_price"),
        Index("ix_seats_event_status", "event_id", "status"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id", ondelete="CASCADE"))
    section: Mapped[str] = mapped_column(String(30))
    row_label: Mapped[str] = mapped_column(String(3))
    number: Mapped[int]
    price: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    status: Mapped[str] = mapped_column(String(10), default=SeatStatus.AVAILABLE, server_default=SeatStatus.AVAILABLE)


class Hold(Base):
    """A temporary (5 minute) reservation of one seat by one user."""

    __tablename__ = "holds"
    __table_args__ = (
        CheckConstraint(
            in_list("status", [HoldStatus.ACTIVE, HoldStatus.EXPIRED, HoldStatus.RELEASED, HoldStatus.USED]),
            name="ck_holds_status",
        ),
        # DATABASE-LEVEL GUARANTEE: a seat can never have two ACTIVE holds at once.
        Index("uq_holds_one_active_per_seat", "seat_id", unique=True, postgresql_where=text("status = 'ACTIVE'")),
        Index("ix_holds_user_status", "user_id", "status"),
        Index("ix_holds_active_expiry", "expires_at", postgresql_where=text("status = 'ACTIVE'")),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    seat_id: Mapped[int] = mapped_column(ForeignKey("seats.id", ondelete="CASCADE"))
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id", ondelete="CASCADE"), index=True)
    status: Mapped[str] = mapped_column(String(10), default=HoldStatus.ACTIVE, server_default=HoldStatus.ACTIVE)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"))
