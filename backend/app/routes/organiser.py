from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.middleware.auth import require_organiser
from app.models import Booking, BookingItem, Event, Seat, User
from app.models.constants import BookingStatus, ItemStatus, Role, SeatStatus
from app.schemas.dashboard import EventBookingRow, EventStats, OrganiserSummary
from app.schemas.event import EventPage
from app.services import event_service
from app.utils.errors import AppError

router = APIRouter(prefix="/api/organiser", tags=["Organiser Dashboard"])


def _scope(user: User):
    """Organisers see only their own events; an admin using this dashboard sees every event."""
    return [] if user.role == Role.ADMIN else [Event.organiser_id == user.id]


@router.get("/summary", response_model=OrganiserSummary)
def summary(user: User = Depends(require_organiser), db: Session = Depends(get_db)):
    scope = _scope(user)
    total_events = db.scalar(select(func.count()).select_from(Event).where(*scope)) or 0
    sold, revenue, bookings = db.execute(
        select(func.count(BookingItem.id), func.coalesce(func.sum(BookingItem.price), 0),
               func.count(func.distinct(BookingItem.booking_id)))
        .join(Booking, Booking.id == BookingItem.booking_id).join(Event, Event.id == Booking.event_id)
        .where(BookingItem.status == ItemStatus.CONFIRMED, *scope)).one()
    return OrganiserSummary(total_events=total_events, tickets_sold=sold, total_bookings=bookings, total_revenue=revenue)


@router.get("/events", response_model=EventPage, summary="My events (all statuses)")
def my_events(page: int = Query(1, ge=1), page_size: int = Query(50, ge=1, le=100), q: str | None = None,
              user: User = Depends(require_organiser), db: Session = Depends(get_db)):
    return event_service.search_events(
        db, q=q, page=page, page_size=page_size, sort="date_desc", include_past=True,
        organiser_id=None if user.role == Role.ADMIN else user.id)


@router.get("/events/stats", response_model=list[EventStats], summary="Per-event sales and seat availability")
def event_stats(user: User = Depends(require_organiser), db: Session = Depends(get_db)):
    events = db.scalars(select(Event).where(*_scope(user)).order_by(Event.starts_at.desc())).unique().all()
    ids = [e.id for e in events]
    seat_rows = {r[0]: r for r in db.execute(
        select(Seat.event_id, func.count(), func.count().filter(Seat.status == SeatStatus.BOOKED),
               func.count().filter(Seat.status == SeatStatus.HELD),
               func.count().filter(Seat.status == SeatStatus.AVAILABLE)).where(Seat.event_id.in_(ids)).group_by(Seat.event_id))}
    revenue = dict(db.execute(
        select(Booking.event_id, func.coalesce(func.sum(BookingItem.price), 0))
        .join(Booking, Booking.id == BookingItem.booking_id)
        .where(BookingItem.status == ItemStatus.CONFIRMED, Booking.event_id.in_(ids)).group_by(Booking.event_id)).all())
    out = []
    for e in events:
        total, booked, held, available = seat_rows.get(e.id, (e.id, 0, 0, 0, 0))[1:]
        out.append(EventStats(event_id=e.id, title=e.title, starts_at=e.starts_at, status=e.status, total_seats=total,
                              booked=booked, held=held, available=available, revenue=revenue.get(e.id, 0)))
    return out


@router.get("/events/{event_id}/bookings", response_model=list[EventBookingRow])
def event_bookings(event_id: int, user: User = Depends(require_organiser), db: Session = Depends(get_db)):
    event = db.get(Event, event_id)
    if event is None:
        raise AppError(404, "Event not found")
    if user.role != Role.ADMIN and event.organiser_id != user.id:
        raise AppError(403, "You can only view bookings for your own events")
    rows = db.execute(select(Booking, User).join(User, User.id == Booking.user_id)
                      .where(Booking.event_id == event_id, Booking.status.in_([BookingStatus.CONFIRMED, BookingStatus.CANCELLED]))
                      .order_by(Booking.created_at.desc())).unique().all()
    return [EventBookingRow(
        booking_id=b.id, reference=b.reference, attendee_name=u.name, attendee_email=u.email,
        seats=[f"{i.seat.section} {i.seat.row_label}{i.seat.number}" for i in b.items],
        amount=b.total_amount, created_at=b.created_at, status=b.status) for b, u in rows]
