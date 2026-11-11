import secrets
from datetime import date
from pathlib import Path

from fastapi import APIRouter, Depends, File, Query, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.middleware.auth import get_optional_user, require_organiser
from app.models import Booking, Event, Venue
from app.models import User
from app.models.constants import EventStatus, Role
from app.schemas.event import (CATEGORIES, EventCreate, EventDetail, EventPage, EventUpdate, FilterOptions)
from app.schemas.seat import SeatMapOut
from app.services import event_service, seat_service
from app.utils.errors import AppError

router = APIRouter(prefix="/api/events", tags=["Events"])
UPLOAD_DIR = Path(__file__).resolve().parent.parent / "static" / "uploads"
ALLOWED_IMAGES = {"image/png": ".png", "image/jpeg": ".jpg", "image/webp": ".webp"}


def _owned_event(db: Session, event_id: int, user: User) -> Event:
    """Load an event that the user is allowed to manage (owner or admin)."""
    event = db.get(Event, event_id)
    if event is None:
        raise AppError(404, "Event not found")
    if user.role != Role.ADMIN and event.organiser_id != user.id:
        raise AppError(403, "You can only manage your own events")
    return event


@router.get("", response_model=EventPage)
def list_events(
    q: str | None = Query(None, description="Search by event name"),
    city: str | None = None,
    category: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    sort: str = Query("date", pattern="^(date|date_desc|popular)$"),
    page: int = Query(1, ge=1),
    page_size: int = Query(12, ge=1, le=50),
    db: Session = Depends(get_db),
):
    """Public list of upcoming, approved events with search, filters and pagination."""
    return event_service.search_events(db, q=q, city=city, category=category, date_from=date_from, date_to=date_to,
                                       page=page, page_size=page_size, sort=sort,
                                       statuses=[EventStatus.APPROVED])


@router.get("/filters", response_model=FilterOptions)
def filter_options(db: Session = Depends(get_db)):
    cities = db.scalars(select(Venue.city).join(Event, Event.venue_id == Venue.id)
                        .where(Event.status == EventStatus.APPROVED).distinct().order_by(Venue.city)).all()
    return FilterOptions(cities=list(cities), categories=CATEGORIES)


@router.post("/upload-image", tags=["Events"])
def upload_image(file: UploadFile = File(...), _: User = Depends(require_organiser)):
    """Upload an event poster (PNG/JPEG/WebP, max 3 MB). Returns the URL to use as `image_url`."""
    ext = ALLOWED_IMAGES.get(file.content_type or "")
    if ext is None:
        raise AppError(415, "Only PNG, JPEG or WebP images are allowed")
    data = file.file.read(3 * 1024 * 1024 + 1)
    if len(data) > 3 * 1024 * 1024:
        raise AppError(413, "Image must be smaller than 3 MB")
    name = secrets.token_hex(12) + ext
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    (UPLOAD_DIR / name).write_bytes(data)
    return {"url": f"/static/uploads/{name}"}


@router.post("", response_model=EventDetail, status_code=status.HTTP_201_CREATED)
def create_event(data: EventCreate, user: User = Depends(require_organiser), db: Session = Depends(get_db)):
    """Create an event together with its seats. Organiser events wait for admin approval (configurable)."""
    event = event_service.create_event(db, user, data)
    return event_service.to_detail(db, event)


@router.get("/{event_id}", response_model=EventDetail)
def get_event(event_id: int, user: User | None = Depends(get_optional_user), db: Session = Depends(get_db)):
    event = db.get(Event, event_id)
    if event is None:
        raise AppError(404, "Event not found")
    visible = event.status in (EventStatus.APPROVED, EventStatus.CANCELLED) or (
        user is not None and (user.role == Role.ADMIN or user.id == event.organiser_id))
    if not visible:
        raise AppError(404, "Event not found")
    return event_service.to_detail(db, event)


@router.put("/{event_id}", response_model=EventDetail)
def update_event(event_id: int, data: EventUpdate, user: User = Depends(require_organiser),
                 db: Session = Depends(get_db)):
    event = _owned_event(db, event_id, user)
    event_service.update_event(db, event, data)
    return event_service.to_detail(db, event)


@router.delete("/{event_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_event(event_id: int, user: User = Depends(require_organiser), db: Session = Depends(get_db)):
    event = _owned_event(db, event_id, user)
    if db.scalar(select(Booking.id).where(Booking.event_id == event.id).limit(1)):
        raise AppError(409, "This event already has bookings and cannot be deleted. Cancel it instead.")
    db.delete(event)
    db.commit()


@router.get("/{event_id}/seats", response_model=SeatMapOut, tags=["Seats"])
def seat_map(event_id: int, user: User | None = Depends(get_optional_user), db: Session = Depends(get_db)):
    """Seat map grouped by section and row, with the live status of every seat."""
    event = db.get(Event, event_id)
    if event is None or event.status not in (EventStatus.APPROVED, EventStatus.CANCELLED):
        raise AppError(404, "Event not found")
    return seat_service.get_seat_map(db, event)
