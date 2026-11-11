from datetime import datetime
from decimal import Decimal

from sqlalchemy import (Boolean, CheckConstraint, DateTime, ForeignKey, Index, Numeric, String,
                        UniqueConstraint, text)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.base import TimestampMixin
from app.models.constants import BookingStatus, ItemStatus, PaymentStatus, in_list


class Booking(Base, TimestampMixin):
    __tablename__ = "bookings"
    __table_args__ = (
        # Same user + same Idempotency-Key => same booking (never a second one).
        UniqueConstraint("user_id", "idempotency_key", name="uq_booking_idempotency"),
        CheckConstraint(
            in_list("status", [BookingStatus.PENDING_PAYMENT, BookingStatus.CONFIRMED,
                               BookingStatus.CANCELLED, BookingStatus.EXPIRED]),
            name="ck_bookings_status",
        ),
        CheckConstraint(in_list("payment_status", ["UNPAID", "PAID", "REFUNDED"]), name="ck_bookings_payment_status"),
        Index("ix_bookings_user_created", "user_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    reference: Mapped[str] = mapped_column(String(20), unique=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id"), index=True)
    total_amount: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    status: Mapped[str] = mapped_column(String(20), default=BookingStatus.PENDING_PAYMENT)
    payment_status: Mapped[str] = mapped_column(String(10), default="UNPAID", server_default="UNPAID")
    idempotency_key: Mapped[str] = mapped_column(String(100))

    event = relationship("Event", lazy="joined")
    items: Mapped[list["BookingItem"]] = relationship(back_populates="booking", order_by="BookingItem.id")


class BookingItem(Base, TimestampMixin):
    """One seat inside a booking."""

    __tablename__ = "booking_items"
    __table_args__ = (
        CheckConstraint(in_list("status", [ItemStatus.PENDING, ItemStatus.CONFIRMED, ItemStatus.CANCELLED]),
                        name="ck_booking_items_status"),
        # DATABASE-LEVEL GUARANTEE: a seat can have at most ONE confirmed booking item.
        Index("uq_confirmed_item_per_seat", "seat_id", unique=True, postgresql_where=text("status = 'CONFIRMED'")),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    booking_id: Mapped[int] = mapped_column(ForeignKey("bookings.id", ondelete="CASCADE"), index=True)
    seat_id: Mapped[int] = mapped_column(ForeignKey("seats.id"), index=True)
    hold_id: Mapped[int] = mapped_column(ForeignKey("holds.id"), unique=True)
    price: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    status: Mapped[str] = mapped_column(String(10), default=ItemStatus.PENDING)

    booking: Mapped[Booking] = relationship(back_populates="items")
    seat = relationship("Seat", lazy="joined")
    ticket: Mapped["Ticket | None"] = relationship(back_populates="item", uselist=False, lazy="joined")


class Payment(Base, TimestampMixin):
    __tablename__ = "payments"
    __table_args__ = (
        UniqueConstraint("user_id", "idempotency_key", name="uq_payment_idempotency"),
        CheckConstraint(in_list("status", [PaymentStatus.SUCCESS, PaymentStatus.FAILED, PaymentStatus.REFUNDED]),
                        name="ck_payments_status"),
        # DATABASE-LEVEL GUARANTEE: a booking can be paid successfully only once.
        Index("uq_one_paid_payment_per_booking", "booking_id", unique=True,
              postgresql_where=text("status IN ('SUCCESS', 'REFUNDED')")),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    booking_id: Mapped[int] = mapped_column(ForeignKey("bookings.id"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    amount: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    status: Mapped[str] = mapped_column(String(10))
    method: Mapped[str] = mapped_column(String(20), default="MOCK_CARD")
    card_last4: Mapped[str] = mapped_column(String(4))
    provider_ref: Mapped[str | None] = mapped_column(String(40))
    failure_reason: Mapped[str | None] = mapped_column(String(200))
    idempotency_key: Mapped[str] = mapped_column(String(100))


class Ticket(Base):
    __tablename__ = "tickets"

    id: Mapped[int] = mapped_column(primary_key=True)
    booking_item_id: Mapped[int] = mapped_column(ForeignKey("booking_items.id", ondelete="CASCADE"), unique=True)
    code: Mapped[str] = mapped_column(String(64), unique=True, index=True)  # random, non-guessable; this is what the QR holds
    checked_in: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"))
    checked_in_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"))

    item: Mapped[BookingItem] = relationship(back_populates="ticket")
