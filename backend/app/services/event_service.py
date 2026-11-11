"""Event creation, search and summaries."""
import math
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from app.config import settings
from app.models import Event, Seat, User, Venue
from app.models.constants import EventStatus, Role, SeatStatus
from app.schemas.event import (EventCreate, EventDetail, EventOut, EventPage, EventUpdate,
                               SectionSummary)
from app.utils.errors import AppError
from app.utils.timeutil import utcnow


def row_label(index: int) -> str:
    """0 -> A, 1 -> B ... 25 -> Z"""
    return chr(ord("A") + index)


def create_event(db: Session, organiser: User, data: EventCreate) -> Event:
    if data.starts_at <= utcnow():
        raise AppError(422, "Event start time must be in the future")

    if data.venue_id is not None:
        venue = db.get(Venue, data.venue_id)
        if venue is None:
            raise AppError(404, "Venue not found")
    else:
        venue = Venue(**data.venue.model_dump())
        db.add(venue)
        db.flush()

    auto_approve = organiser.role == Role.ADMIN or not settings.require_event_approval
    event = Event(
        organiser_id=organiser.id, venue_id=venue.id, title=data.title.strip(), description=data.description,
        category=data.category, image_url=data.image_url, starts_at=data.starts_at,
        status=EventStatus.APPROVED if auto_approve else EventStatus.PENDING,
    )
    db.add(event)
    db.flush()

    seats = [
        Seat(event_id=event.id, section=sec.name.strip(), row_label=row_label(r), number=n, price=sec.price)
        for sec in data.sections
        for r in range(sec.rows)
        for n in range(1, sec.seats_per_row + 1)
    ]
    db.add_all(seats)
    db.commit()
    return event


def update_event(db: Session, event: Event, data: EventUpdate) -> Event:
    fields = data.model_dump(exclude_unset=True)
    if fields.get("starts_at") and fields["starts_at"] <= utcnow():
        raise AppError(422, "Event start time must be in the future")
    for key in ("title", "description", "category", "image_url", "starts_at"):
        if key in fields and fields[key] is not None:
            setattr(event, key, fields[key])
    if data.cancel:
        event.status = EventStatus.CANCELLED
    if data.section_prices:
        for section, price in data.section_prices.items():
            if price < 0:
                raise AppError(422, "Price cannot be negative")
            # Prices of already-booked seats never change.
            db.query(Seat).filter(Seat.event_id == event.id, Seat.section == section,
                                  Seat.status != SeatStatus.BOOKED).update({Seat.price: price})
    db.commit()
    return event


def _aggregates(db: Session, event_ids: list[int]) -> dict[int, tuple[int, int, Decimal | None]]:
    if not event_ids:
        return {}
    rows = db.execute(
        select(Seat.event_id, func.count(), func.count().filter(Seat.status == SeatStatus.AVAILABLE), func.min(Seat.price))
        .where(Seat.event_id.in_(event_ids)).group_by(Seat.event_id)
    ).all()
    return {r[0]: (r[1], r[2], r[3]) for r in rows}


def to_out(event: Event, agg: tuple[int, int, Decimal | None] | None) -> EventOut:
    total, available, min_price = agg or (0, 0, None)
    return EventOut(
        id=event.id, title=event.title, description=event.description, category=event.category,
        image_url=event.image_url, starts_at=event.starts_at, status=event.status,
        organiser_id=event.organiser_id, venue=event.venue, min_price=min_price,
        total_seats=total, available_seats=available,
    )


def to_detail(db: Session, event: Event) -> EventDetail:
    rows = db.execute(
        select(Seat.section, func.min(Seat.price), func.count(), func.count().filter(Seat.status == SeatStatus.AVAILABLE),
               func.min(Seat.id))
        .where(Seat.event_id == event.id).group_by(Seat.section).order_by(func.min(Seat.id))
    ).all()
    sections = [SectionSummary(name=r[0], price=r[1], total=r[2], available=r[3]) for r in rows]
    base = to_out(event, (sum(s.total for s in sections), sum(s.available for s in sections),
                          min((s.price for s in sections), default=None)))
    return EventDetail(**base.model_dump(), sections=sections)


def _day_bounds(d: date, end: bool) -> datetime:
    tz = ZoneInfo(settings.local_timezone)
    if end:
        return datetime.combine(d + timedelta(days=1), time.min, tzinfo=tz)
    return datetime.combine(d, time.min, tzinfo=tz)


def search_events(
    db: Session, *, q: str | None = None, city: str | None = None, category: str | None = None,
    date_from: date | None = None, date_to: date | None = None, page: int = 1, page_size: int = 12,
    sort: str = "date", statuses: list[str] | None = None, organiser_id: int | None = None,
    include_past: bool = False,
) -> EventPage:
    stmt: Select = select(Event).join(Venue, Event.venue_id == Venue.id)
    if statuses:
        stmt = stmt.where(Event.status.in_(statuses))
    if organiser_id is not None:
        stmt = stmt.where(Event.organiser_id == organiser_id)
    if q:
        stmt = stmt.where(Event.title.ilike(f"%{q.strip()}%"))
    if city:
        stmt = stmt.where(func.lower(Venue.city) == city.strip().lower())
    if category:
        stmt = stmt.where(func.lower(Event.category) == category.strip().lower())
    if date_from:
        stmt = stmt.where(Event.starts_at >= _day_bounds(date_from, end=False))
    if date_to:
        stmt = stmt.where(Event.starts_at < _day_bounds(date_to, end=True))
    if not include_past:
        stmt = stmt.where(Event.starts_at >= utcnow())

    total = db.scalar(select(func.count()).select_from(stmt.order_by(None).subquery())) or 0

    if sort == "popular":
        taken = (select(Seat.event_id.label("eid"), func.count().label("taken"))
                 .where(Seat.status != SeatStatus.AVAILABLE).group_by(Seat.event_id).subquery())
        stmt = stmt.outerjoin(taken, taken.c.eid == Event.id).order_by(
            func.coalesce(taken.c.taken, 0).desc(), Event.starts_at)
    elif sort == "date_desc":
        stmt = stmt.order_by(Event.starts_at.desc())
    else:
        stmt = stmt.order_by(Event.starts_at, Event.id)

    events = db.scalars(stmt.limit(page_size).offset((page - 1) * page_size)).unique().all()
    aggs = _aggregates(db, [e.id for e in events])
    return EventPage(items=[to_out(e, aggs.get(e.id)) for e in events], total=total, page=page,
                     page_size=page_size, pages=max(1, math.ceil(total / page_size)))
