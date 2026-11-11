from datetime import datetime
from zoneinfo import ZoneInfo

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.config import settings
from app.models import Booking, BookingItem, Event, Ticket, User
from app.models.constants import BookingStatus, ItemStatus, Role
from app.utils.errors import AppError
from app.utils.ticket_files import make_ticket_png
from app.utils.timeutil import utcnow


def get_ticket_for_user(db: Session, user: User, ticket_id: int) -> Ticket:
    ticket = db.get(Ticket, ticket_id)
    if ticket is None or ticket.item.booking.user_id != user.id:
        raise AppError(404, "Ticket not found")
    return ticket


def list_tickets(db: Session, user: User) -> list[Ticket]:
    return list(db.scalars(
        select(Ticket).join(BookingItem, BookingItem.id == Ticket.booking_item_id)
        .join(Booking, Booking.id == BookingItem.booking_id).join(Event, Event.id == Booking.event_id)
        .where(Booking.user_id == user.id).order_by(Event.starts_at.desc(), Ticket.id)).unique())


def ticket_image(ticket: Ticket) -> bytes:
    item, event = ticket.item, ticket.item.booking.event
    local = event.starts_at.astimezone(ZoneInfo(settings.local_timezone))
    return make_ticket_png(
        event_title=event.title, when=local.strftime("%a, %d %b %Y  %I:%M %p"),
        venue=f"{event.venue.name}, {event.venue.city}",
        seat=f"{item.seat.section} - Row {item.seat.row_label} - Seat {item.seat.number}",
        reference=item.booking.reference, code=ticket.code)


def check_in(db: Session, user: User, code: str) -> Ticket:
    """Entry validation: marks the ticket used exactly once (a second scan is rejected)."""
    ticket = db.scalar(select(Ticket).where(Ticket.code == code))
    if ticket is None:
        raise AppError(404, "Invalid ticket code")
    event = ticket.item.booking.event
    if user.role != Role.ADMIN and event.organiser_id != user.id:
        raise AppError(403, "You can only check in tickets for your own events")
    if ticket.item.status != ItemStatus.CONFIRMED or ticket.item.booking.status != BookingStatus.CONFIRMED:
        raise AppError(409, "This ticket is not valid (booking cancelled)")
    # Atomic "claim": only one scan can flip checked_in from false to true.
    claimed = db.execute(update(Ticket).where(Ticket.id == ticket.id, Ticket.checked_in.is_(False))
                         .values(checked_in=True, checked_in_at=utcnow()).returning(Ticket.id)).first()
    db.commit()
    if claimed is None:
        raise AppError(409, "This ticket has already been used")
    db.refresh(ticket)
    return ticket
