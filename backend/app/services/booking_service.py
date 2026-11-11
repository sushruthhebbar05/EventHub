"""Checkout (create booking), mock payment, cancellation, and the read models for bookings/tickets.

Lock order everywhere: booking row -> seat rows (ascending id) -> hold rows. Never the reverse.
"""
import secrets
from datetime import timedelta
from decimal import Decimal

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import settings
from app.models import Booking, BookingItem, Hold, Payment, Seat, Ticket, User
from app.models.constants import BookingStatus, HoldStatus, ItemStatus, PaymentStatus, SeatStatus
from app.schemas.booking import (BookingItemOut, BookingOut, EventBrief, PaymentIn, PaymentOut,
                                 TicketBrief, TicketOut)
from app.services.seat_service import broadcast
from app.utils import payment_gateway
from app.utils.errors import AppError
from app.utils.timeutil import utcnow


# ------------------------------------------------------------------ read models
def event_brief(event) -> EventBrief:
    return EventBrief(id=event.id, title=event.title, starts_at=event.starts_at, image_url=event.image_url,
                      venue_name=event.venue.name, city=event.venue.city)


def booking_to_out(db: Session, booking: Booking) -> BookingOut:
    expires_at = None
    if booking.status == BookingStatus.PENDING_PAYMENT:
        expires_at = db.scalar(select(Hold.expires_at).where(
            Hold.id.in_([i.hold_id for i in booking.items])).order_by(Hold.expires_at).limit(1))
    items = [BookingItemOut(
        id=i.id, seat_id=i.seat_id, section=i.seat.section, row_label=i.seat.row_label, number=i.seat.number,
        price=i.price, status=i.status,
        ticket=TicketBrief(id=i.ticket.id, code=i.ticket.code, checked_in=i.ticket.checked_in) if i.ticket else None,
    ) for i in booking.items]
    return BookingOut(id=booking.id, reference=booking.reference, status=booking.status,
                      payment_status=booking.payment_status, total_amount=booking.total_amount,
                      created_at=booking.created_at, expires_at=expires_at,
                      event=event_brief(booking.event), items=items)


def ticket_to_out(ticket: Ticket) -> TicketOut:
    item = ticket.item
    if item.status == ItemStatus.CANCELLED:
        status = "CANCELLED"
    elif ticket.checked_in:
        status = "USED"
    else:
        status = "VALID"
    return TicketOut(id=ticket.id, code=ticket.code, status=status, checked_in=ticket.checked_in,
                     checked_in_at=ticket.checked_in_at, section=item.seat.section, row_label=item.seat.row_label,
                     number=item.seat.number, price=item.price, booking_reference=item.booking.reference,
                     event=event_brief(item.booking.event))


def get_booking_for_user(db: Session, user: User, booking_id: int) -> Booking:
    booking = db.get(Booking, booking_id)
    if booking is None or booking.user_id != user.id:
        raise AppError(404, "Booking not found")
    return booking


# ------------------------------------------------------------------ create booking (checkout)
def create_booking(db: Session, user: User, hold_ids: list[int], idempotency_key: str) -> tuple[Booking, bool]:
    """Returns (booking, created). Repeating the same request with the same key returns the same booking."""
    existing = db.scalar(select(Booking).where(Booking.user_id == user.id, Booking.idempotency_key == idempotency_key))
    if existing:
        return existing, False

    ids = sorted(set(hold_ids))
    holds_preview = db.scalars(select(Hold).where(Hold.id.in_(ids), Hold.user_id == user.id)).all()
    if len(holds_preview) != len(ids):
        raise AppError(404, "One or more holds were not found")

    # Lock the seats first (same order as every other writer), then judge the holds.
    seat_ids = sorted(h.seat_id for h in holds_preview)
    seats = {s.id: s for s in db.scalars(select(Seat).where(Seat.id.in_(seat_ids)).order_by(Seat.id).with_for_update())}
    # Re-check the idempotency key now that we hold the lock: an identical request that was racing us has
    # either committed already (so we return ITS booking) or will wait for us. Never an error for a true duplicate.
    existing = db.scalar(select(Booking).where(Booking.user_id == user.id, Booking.idempotency_key == idempotency_key))
    if existing:
        return existing, False
    holds = db.scalars(select(Hold).where(Hold.id.in_(ids), Hold.user_id == user.id).order_by(Hold.id)).all()

    now = utcnow()
    if len({h.event_id for h in holds}) != 1:
        raise AppError(422, "All seats in one booking must belong to the same event")
    for h in holds:
        if h.status != HoldStatus.ACTIVE or h.expires_at <= now:
            raise AppError(410, "Your seat hold has expired. Please select your seats again.", {"hold_id": h.id})
    already = db.scalar(select(BookingItem.id).where(BookingItem.hold_id.in_(ids)).limit(1))
    if already:
        raise AppError(409, "These seats are already part of another booking")

    total = sum((seats[h.seat_id].price for h in holds), Decimal("0"))
    booking = Booking(reference="EH" + secrets.token_hex(4).upper(), user_id=user.id, event_id=holds[0].event_id,
                      total_amount=total, status=BookingStatus.PENDING_PAYMENT, idempotency_key=idempotency_key)
    booking.items = [BookingItem(seat_id=h.seat_id, hold_id=h.id, price=seats[h.seat_id].price,
                                 status=ItemStatus.PENDING) for h in holds]
    db.add(booking)
    try:
        db.commit()
    except IntegrityError:
        # Two identical requests raced each other; the loser simply returns the winner's booking.
        db.rollback()
        existing = db.scalar(select(Booking).where(Booking.user_id == user.id,
                                                   Booking.idempotency_key == idempotency_key))
        if existing:
            return existing, False
        raise AppError(409, "These seats are already part of another booking")
    return booking, True


# ------------------------------------------------------------------ payment
def pay_for_booking(db: Session, user: User, data: PaymentIn, idempotency_key: str) -> tuple[Payment, bool]:
    """Returns (payment, created). Raises AppError(402) when the mock gateway declines."""
    prior = db.scalar(select(Payment).where(Payment.user_id == user.id, Payment.idempotency_key == idempotency_key))
    if prior:
        if prior.booking_id != data.booking_id:
            raise AppError(422, "This Idempotency-Key was already used for a different booking")
        return prior, False

    # (1) lock the booking row: two payments for the same booking are now strictly serialised.
    booking = db.scalar(select(Booking).where(Booking.id == data.booking_id).with_for_update(of=Booking))
    if booking is None or booking.user_id != user.id:
        raise AppError(404, "Booking not found")
    if booking.status == BookingStatus.CONFIRMED:
        raise AppError(409, "This booking has already been paid")
    if booking.status != BookingStatus.PENDING_PAYMENT:
        raise AppError(409, f"This booking is {booking.status.lower().replace('_', ' ')} and can no longer be paid")

    # (2) lock the seats, then verify that every hold is still active, still ours and not expired.
    items = list(booking.items)
    seat_ids = sorted(i.seat_id for i in items)
    seats = {s.id: s for s in db.scalars(select(Seat).where(Seat.id.in_(seat_ids)).order_by(Seat.id).with_for_update())}
    holds = {h.id: h for h in db.scalars(select(Hold).where(Hold.id.in_([i.hold_id for i in items])))}
    now = utcnow()
    for item in items:
        h = holds[item.hold_id]
        if h.user_id != user.id or h.status != HoldStatus.ACTIVE or h.expires_at <= now \
                or seats[item.seat_id].status != SeatStatus.HELD:
            _expire_booking(db, booking, items, holds, seats)
            raise AppError(410, "Your seat hold expired before payment. The seats have been released.")

    # (3) the (mock) payment gateway
    result = payment_gateway.charge(data.card_number, booking.total_amount)
    last4 = data.card_number[-4:]
    if not result.approved:
        db.add(Payment(booking_id=booking.id, user_id=user.id, amount=booking.total_amount, status=PaymentStatus.FAILED,
                       card_last4=last4, failure_reason=result.failure_reason, idempotency_key=idempotency_key))
        db.commit()  # seats stay held so the user can retry with another card
        raise AppError(402, result.failure_reason or "Payment failed")

    # (4) confirm everything in ONE transaction
    payment = Payment(booking_id=booking.id, user_id=user.id, amount=booking.total_amount, status=PaymentStatus.SUCCESS,
                      card_last4=last4, provider_ref=result.reference, idempotency_key=idempotency_key)
    db.add(payment)
    changed = {}
    for item in items:
        item.status = ItemStatus.CONFIRMED
        seats[item.seat_id].status = SeatStatus.BOOKED
        holds[item.hold_id].status = HoldStatus.USED
        item.ticket = Ticket(code=secrets.token_urlsafe(24))  # unguessable, 192 bits of randomness
        changed[item.seat_id] = SeatStatus.BOOKED
    booking.status = BookingStatus.CONFIRMED
    booking.payment_status = "PAID"
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise AppError(409, "These seats were just taken by another booking")
    broadcast({booking.event_id: changed})
    return payment, True


def _expire_booking(db, booking, items, holds, seats) -> None:
    changed = {}
    for item in items:
        item.status = ItemStatus.CANCELLED
        h = holds[item.hold_id]
        if h.status == HoldStatus.ACTIVE:
            h.status = HoldStatus.EXPIRED
        if seats[item.seat_id].status == SeatStatus.HELD:
            seats[item.seat_id].status = SeatStatus.AVAILABLE
            changed[item.seat_id] = SeatStatus.AVAILABLE
    booking.status = BookingStatus.EXPIRED
    db.commit()
    broadcast({booking.event_id: changed})


def payment_to_out(db: Session, payment: Payment) -> PaymentOut:
    booking = db.get(Booking, payment.booking_id)
    return PaymentOut(id=payment.id, booking_id=payment.booking_id, amount=payment.amount, status=payment.status,
                      card_last4=payment.card_last4, provider_ref=payment.provider_ref,
                      created_at=payment.created_at, booking=booking_to_out(db, booking))


# ------------------------------------------------------------------ cancellation
def cancel_booking(db: Session, user: User, booking_id: int) -> Booking:
    booking = db.scalar(select(Booking).where(Booking.id == booking_id).with_for_update(of=Booking))
    if booking is None or booking.user_id != user.id:
        raise AppError(404, "Booking not found")
    items = list(booking.items)
    seat_ids = sorted(i.seat_id for i in items)
    seats = {s.id: s for s in db.scalars(select(Seat).where(Seat.id.in_(seat_ids)).order_by(Seat.id).with_for_update())}
    changed = {}

    if booking.status == BookingStatus.PENDING_PAYMENT:
        # Abandoning checkout: release the holds.
        for item in items:
            item.status = ItemStatus.CANCELLED
            db.execute(update(Hold).where(Hold.id == item.hold_id, Hold.status == HoldStatus.ACTIVE)
                       .values(status=HoldStatus.RELEASED))
            if seats[item.seat_id].status == SeatStatus.HELD:
                seats[item.seat_id].status = SeatStatus.AVAILABLE
                changed[item.seat_id] = SeatStatus.AVAILABLE
        booking.status = BookingStatus.CANCELLED
    elif booking.status == BookingStatus.CONFIRMED:
        cutoff = booking.event.starts_at - timedelta(hours=settings.cancel_cutoff_hours)
        if utcnow() >= cutoff:
            raise AppError(409, f"Bookings can only be cancelled up to {settings.cancel_cutoff_hours} hours before the event")
        if any(i.ticket and i.ticket.checked_in for i in items):
            raise AppError(409, "A ticket in this booking has already been used")
        for item in items:   # this is the ONLY place a BOOKED seat is deliberately freed
            item.status = ItemStatus.CANCELLED
            seats[item.seat_id].status = SeatStatus.AVAILABLE
            changed[item.seat_id] = SeatStatus.AVAILABLE
        booking.status = BookingStatus.CANCELLED
        booking.payment_status = "REFUNDED"
        db.execute(update(Payment).where(Payment.booking_id == booking.id, Payment.status == PaymentStatus.SUCCESS)
                   .values(status=PaymentStatus.REFUNDED))
    else:
        raise AppError(409, f"A {booking.status.lower().replace('_', ' ')} booking cannot be cancelled")
    db.commit()
    broadcast({booking.event_id: changed})
    return booking
