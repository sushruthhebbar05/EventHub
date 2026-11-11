from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from app.database import get_db
from app.middleware.auth import get_current_user, require_organiser
from app.models import User
from app.schemas.booking import CheckInIn, CheckInOut, TicketOut
from app.services import booking_service, ticket_service
from app.utils.ticket_files import make_qr_png

router = APIRouter(prefix="/api/tickets", tags=["Tickets"])


@router.get("", response_model=list[TicketOut])
def my_tickets(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """All tickets you have bought (past and upcoming)."""
    return [booking_service.ticket_to_out(t) for t in ticket_service.list_tickets(db, user)]


# NOTE: defined before "/{ticket_id}" routes so "check-in" is never parsed as an id.
@router.post("/check-in", response_model=CheckInOut, tags=["Tickets"])
def check_in(data: CheckInIn, user: User = Depends(require_organiser), db: Session = Depends(get_db)):
    """Entry validation (organiser/admin): marks a ticket as used. A second scan returns 409."""
    ticket = ticket_service.check_in(db, user, data.code)
    return CheckInOut(message="Ticket is valid - entry granted", ticket=booking_service.ticket_to_out(ticket))


@router.get("/{ticket_id}", response_model=TicketOut)
def ticket_details(ticket_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return booking_service.ticket_to_out(ticket_service.get_ticket_for_user(db, user, ticket_id))


@router.get("/{ticket_id}/qr", response_class=Response, responses={200: {"content": {"image/png": {}}}})
def ticket_qr(ticket_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """The QR code PNG. It encodes only the random ticket code."""
    ticket = ticket_service.get_ticket_for_user(db, user, ticket_id)
    return Response(content=make_qr_png(ticket.code), media_type="image/png",
                    headers={"Cache-Control": "private, max-age=3600"})


@router.get("/{ticket_id}/download", response_class=Response, responses={200: {"content": {"image/png": {}}}})
def ticket_download(ticket_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """A printable ticket image (PNG) with the QR code."""
    ticket = ticket_service.get_ticket_for_user(db, user, ticket_id)
    return Response(content=ticket_service.ticket_image(ticket), media_type="image/png",
                    headers={"Content-Disposition": f'attachment; filename="eventhub-ticket-{ticket.id}.png"'})
