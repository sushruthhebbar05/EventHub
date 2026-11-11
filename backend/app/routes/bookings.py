from fastapi import APIRouter, Depends, Header, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.middleware.auth import get_current_user
from app.models import Booking, User
from app.schemas.booking import BookingCreate, BookingOut
from app.services import booking_service

router = APIRouter(prefix="/api/bookings", tags=["Bookings"])


@router.post("", response_model=BookingOut, status_code=status.HTTP_201_CREATED)
def create_booking(data: BookingCreate, response: Response,
                   idempotency_key: str = Header(..., alias="Idempotency-Key", min_length=8, max_length=100),
                   user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Turn active holds into a booking awaiting payment.

    Send a unique `Idempotency-Key` header. Repeating the request with the same key returns the same booking
    (HTTP 200) instead of creating a second one.
    """
    booking, created = booking_service.create_booking(db, user, data.hold_ids, idempotency_key)
    if not created:
        response.status_code = status.HTTP_200_OK
    return booking_service.booking_to_out(db, booking)


@router.get("", response_model=list[BookingOut])
def my_bookings(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    bookings = db.scalars(select(Booking).where(Booking.user_id == user.id).order_by(Booking.created_at.desc())).unique().all()
    return [booking_service.booking_to_out(db, b) for b in bookings]


@router.get("/{booking_id}", response_model=BookingOut)
def booking_details(booking_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return booking_service.booking_to_out(db, booking_service.get_booking_for_user(db, user, booking_id))


@router.post("/{booking_id}/cancel", response_model=BookingOut)
def cancel_booking(booking_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Cancel an unpaid checkout (releases the seats) or a paid booking (refund + seats released)."""
    return booking_service.booking_to_out(db, booking_service.cancel_booking(db, user, booking_id))
