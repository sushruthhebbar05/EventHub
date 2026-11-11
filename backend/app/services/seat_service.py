"""Seat map + timed seat holds.

THE CONCURRENCY STRATEGY (explain this to the panel):
  1. Every request that changes seat state first runs `SELECT ... FROM seats WHERE id IN (...) ORDER BY id FOR UPDATE`.
     PostgreSQL makes the second request WAIT on that row until the first transaction commits.
  2. After the lock is acquired we re-read the *committed* state (READ COMMITTED isolation), so the second
     request sees the seat as HELD/BOOKED and gets HTTP 409.
  3. Rows are always locked in ascending id order -> two requests for overlapping seats cannot deadlock.
  4. Partial UNIQUE indexes are a second safety net: even a bug in the Python code could not create two ACTIVE
     holds on a seat, or two CONFIRMED booking items for a seat.
"""
from collections import defaultdict
from datetime import timedelta

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.config import settings
from app.database import SessionLocal
from app.models import Booking, BookingItem, Event, Hold, Seat, User
from app.models.constants import BookingStatus, EventStatus, HoldStatus, ItemStatus, SeatStatus
from app.schemas.seat import HoldOut, RowOut, SeatMapOut, SeatOut, SectionOut
from app.utils.errors import AppError
from app.utils.timeutil import utcnow
from app.websocket.manager import manager


def broadcast(changes: dict[int, dict[int, str]]) -> None:
    """changes = {event_id: {seat_id: new_status}}"""
    for event_id, seat_status in changes.items():
        manager.notify(event_id, list(seat_status), seat_status)


def hold_to_out(hold: Hold, seat: Seat) -> HoldOut:
    return HoldOut(id=hold.id, seat_id=hold.seat_id, event_id=hold.event_id, status=hold.status,
                   expires_at=hold.expires_at, section=seat.section, row_label=seat.row_label,
                   number=seat.number, price=seat.price)


# ---------------------------------------------------------------- seat map
def get_seat_map(db: Session, event: Event) -> SeatMapOut:
    now = utcnow()
    seats = db.scalars(select(Seat).where(Seat.event_id == event.id)
                       .order_by(Seat.id)).all()
    live_holds = set(db.scalars(select(Hold.seat_id).where(
        Hold.event_id == event.id, Hold.status == HoldStatus.ACTIVE, Hold.expires_at > now)))

    sections: dict[str, dict] = {}
    for s in seats:
        # A HELD seat whose hold has run out but hasn't been swept yet is shown as AVAILABLE.
        status = s.status
        if status == SeatStatus.HELD and s.id not in live_holds:
            status = SeatStatus.AVAILABLE
        sec = sections.setdefault(s.section, {"price": s.price, "rows": defaultdict(list)})
        sec["rows"][s.row_label].append(SeatOut(id=s.id, number=s.number, status=status))

    return SeatMapOut(event_id=event.id, sections=[
        SectionOut(name=name, price=sec["price"],
                   rows=[RowOut(label=label, seats=sorted(row, key=lambda x: x.number))
                         for label, row in sorted(sec["rows"].items())])
        for name, sec in sections.items()
    ])


# ---------------------------------------------------------------- create holds
def create_holds(db: Session, user: User, event_id: int, seat_ids: list[int]) -> list[HoldOut]:
    ids = sorted(set(seat_ids))
    if len(ids) > settings.max_seats_per_booking:
        raise AppError(422, f"You can hold at most {settings.max_seats_per_booking} seats at a time")

    event = db.get(Event, event_id)
    if event is None or event.status != EventStatus.APPROVED:
        raise AppError(404, "Event not found")
    now = utcnow()
    if event.starts_at <= now:
        raise AppError(409, "This event has already started")

    # (1) LOCK the seat rows. A concurrent request for the same seat now waits here.
    seats = db.scalars(select(Seat).where(Seat.id.in_(ids), Seat.event_id == event_id)
                       .order_by(Seat.id).with_for_update()).all()
    if len(seats) != len(ids):
        raise AppError(404, "One or more seats do not exist for this event")

    # (2) Holds that already ran out are marked EXPIRED so they no longer block anybody.
    db.execute(update(Hold).where(Hold.seat_id.in_(ids), Hold.status == HoldStatus.ACTIVE,
                                  Hold.expires_at <= now).values(status=HoldStatus.EXPIRED))
    active = {h.seat_id: h for h in db.scalars(
        select(Hold).where(Hold.seat_id.in_(ids), Hold.status == HoldStatus.ACTIVE))}

    # (3) Decide - while still holding the lock.
    unavailable = [s.id for s in seats
                   if s.status == SeatStatus.BOOKED or (s.id in active and active[s.id].user_id != user.id)]
    if unavailable:
        raise AppError(409, "Some of the selected seats are no longer available", {"seat_ids": unavailable})

    already_mine = db.scalar(select(func.count()).where(
        Hold.user_id == user.id, Hold.event_id == event_id, Hold.status == HoldStatus.ACTIVE,
        Hold.expires_at > now, Hold.seat_id.not_in(ids))) or 0
    if already_mine + len(ids) > settings.max_seats_per_booking:
        raise AppError(422, f"You can hold at most {settings.max_seats_per_booking} seats at a time")

    # (4) Write.
    expires_at = now + timedelta(seconds=settings.hold_seconds)
    holds, changed = [], {}
    for seat in seats:
        hold = active.get(seat.id)
        if hold is None:
            hold = Hold(user_id=user.id, seat_id=seat.id, event_id=event_id,
                        status=HoldStatus.ACTIVE, expires_at=expires_at)
            db.add(hold)
            seat.status = SeatStatus.HELD
            changed[seat.id] = SeatStatus.HELD
        holds.append((hold, seat))
    db.commit()  # lock released here
    broadcast({event_id: changed})
    return [hold_to_out(h, s) for h, s in holds]


def my_active_holds(db: Session, user: User, event_id: int | None = None) -> list[HoldOut]:
    stmt = (select(Hold, Seat).join(Seat, Seat.id == Hold.seat_id)
            .where(Hold.user_id == user.id, Hold.status == HoldStatus.ACTIVE, Hold.expires_at > utcnow())
            .order_by(Hold.id))
    if event_id is not None:
        stmt = stmt.where(Hold.event_id == event_id)
    return [hold_to_out(h, s) for h, s in db.execute(stmt).all()]


# ---------------------------------------------------------------- release a hold
def release_hold(db: Session, user: User, hold_id: int) -> None:
    hold = db.get(Hold, hold_id)
    if hold is None or hold.user_id != user.id:
        raise AppError(404, "Hold not found")
    seat = db.scalar(select(Seat).where(Seat.id == hold.seat_id).with_for_update())
    db.refresh(hold)  # re-read now that we own the lock
    if hold.status != HoldStatus.ACTIVE:
        raise AppError(409, "This hold is no longer active")
    attached = db.scalar(select(BookingItem.id).join(Booking, Booking.id == BookingItem.booking_id).where(
        BookingItem.hold_id == hold.id, BookingItem.status == ItemStatus.PENDING,
        Booking.status == BookingStatus.PENDING_PAYMENT))
    if attached:
        raise AppError(409, "This seat is part of a checkout in progress - cancel the booking instead")
    hold.status = HoldStatus.RELEASED
    changed = {}
    if seat.status == SeatStatus.HELD:   # never touch a BOOKED seat
        seat.status = SeatStatus.AVAILABLE
        changed[seat.id] = SeatStatus.AVAILABLE
    db.commit()
    broadcast({hold.event_id: changed})


# ---------------------------------------------------------------- expiry sweeper
def sweep_expired_holds() -> dict[int, dict[int, str]]:
    """Release every hold whose time has run out. Called every few seconds by a background task.

    Lock order is the same as everywhere else (seats first), so it cannot deadlock with a booking.
    """
    now = utcnow()
    changes: dict[int, dict[int, str]] = {}
    with SessionLocal() as db:
        seat_ids = list(db.scalars(select(Hold.seat_id).where(
            Hold.status == HoldStatus.ACTIVE, Hold.expires_at <= now)))
        if seat_ids:
            db.scalars(select(Seat.id).where(Seat.id.in_(sorted(seat_ids))).order_by(Seat.id).with_for_update()).all()
            expired = db.execute(
                update(Hold).where(Hold.seat_id.in_(seat_ids), Hold.status == HoldStatus.ACTIVE, Hold.expires_at <= now)
                .values(status=HoldStatus.EXPIRED).returning(Hold.seat_id, Hold.event_id)).all()
            expired_ids = [r[0] for r in expired]
            freed = db.execute(
                update(Seat).where(Seat.id.in_(expired_ids), Seat.status == SeatStatus.HELD)  # only HELD -> AVAILABLE
                .values(status=SeatStatus.AVAILABLE).returning(Seat.id, Seat.event_id)).all()
            db.commit()
            for seat_id, event_id in freed:
                changes.setdefault(event_id, {})[seat_id] = SeatStatus.AVAILABLE

    # Separate transaction: unpaid checkouts whose seats have been lost become EXPIRED.
    with SessionLocal() as db:
        stale = (select(BookingItem.booking_id).join(Hold, Hold.id == BookingItem.hold_id)
                 .where(Hold.status == HoldStatus.EXPIRED, BookingItem.status == ItemStatus.PENDING))
        booking_ids = list(db.scalars(
            update(Booking).where(Booking.status == BookingStatus.PENDING_PAYMENT, Booking.id.in_(stale))
            .values(status=BookingStatus.EXPIRED).returning(Booking.id)))
        if booking_ids:
            db.execute(update(BookingItem).where(BookingItem.booking_id.in_(booking_ids))
                       .values(status=ItemStatus.CANCELLED))
        db.commit()
    return changes
