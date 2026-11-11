from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.middleware.auth import require_admin
from app.models import Booking, BookingItem, Event, User
from app.models.constants import BookingStatus, EventStatus, ItemStatus, Role
from app.schemas.dashboard import AdminStats
from app.schemas.event import EventDetail, EventPage
from app.schemas.user import AdminUserUpdate, UserOut
from app.services import event_service
from app.utils.errors import AppError

router = APIRouter(prefix="/api/admin", tags=["Admin"])


@router.get("/stats", response_model=AdminStats)
def stats(_: User = Depends(require_admin), db: Session = Depends(get_db)):
    role_counts = dict(db.execute(select(User.role, func.count()).group_by(User.role)).all())
    status_counts = dict(db.execute(select(Event.status, func.count()).group_by(Event.status)).all())
    sold, revenue = db.execute(select(func.count(), func.coalesce(func.sum(BookingItem.price), 0))
                               .where(BookingItem.status == ItemStatus.CONFIRMED)).one()
    confirmed = db.scalar(select(func.count()).select_from(Booking).where(Booking.status == BookingStatus.CONFIRMED)) or 0
    return AdminStats(
        users_total=sum(role_counts.values()), attendees=role_counts.get(Role.ATTENDEE, 0),
        organisers=role_counts.get(Role.ORGANISER, 0), admins=role_counts.get(Role.ADMIN, 0),
        events_total=sum(status_counts.values()), events_pending=status_counts.get(EventStatus.PENDING, 0),
        events_approved=status_counts.get(EventStatus.APPROVED, 0), bookings_confirmed=confirmed,
        tickets_sold=sold, revenue=revenue)


@router.get("/users", response_model=list[UserOut])
def list_users(q: str | None = None, _: User = Depends(require_admin), db: Session = Depends(get_db)):
    stmt = select(User).order_by(User.id)
    if q:
        stmt = stmt.where(User.email.ilike(f"%{q}%") | User.name.ilike(f"%{q}%"))
    return db.scalars(stmt.limit(200)).all()


@router.patch("/users/{user_id}", response_model=UserOut)
def update_user(user_id: int, data: AdminUserUpdate, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    user = db.get(User, user_id)
    if user is None:
        raise AppError(404, "User not found")
    if user.id == admin.id and (data.role not in (None, Role.ADMIN) or data.is_active is False):
        raise AppError(409, "You cannot demote or disable your own admin account")
    if data.role is not None:
        user.role = data.role
    if data.is_active is not None:
        user.is_active = data.is_active
    db.commit()
    return user


@router.get("/events", response_model=EventPage, summary="All events, any status")
def all_events(status: str | None = Query(None, pattern="^(PENDING|APPROVED|REJECTED|CANCELLED)$"),
               page: int = Query(1, ge=1), page_size: int = Query(50, ge=1, le=100),
               _: User = Depends(require_admin), db: Session = Depends(get_db)):
    return event_service.search_events(db, page=page, page_size=page_size, sort="date_desc", include_past=True,
                                       statuses=[status] if status else None)


def _set_status(db: Session, event_id: int, new_status: str) -> EventDetail:
    event = db.get(Event, event_id)
    if event is None:
        raise AppError(404, "Event not found")
    event.status = new_status
    db.commit()
    return event_service.to_detail(db, event)


@router.post("/events/{event_id}/approve", response_model=EventDetail)
def approve_event(event_id: int, _: User = Depends(require_admin), db: Session = Depends(get_db)):
    return _set_status(db, event_id, EventStatus.APPROVED)


@router.post("/events/{event_id}/reject", response_model=EventDetail)
def reject_event(event_id: int, _: User = Depends(require_admin), db: Session = Depends(get_db)):
    return _set_status(db, event_id, EventStatus.REJECTED)
