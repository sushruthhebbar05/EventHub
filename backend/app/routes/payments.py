from fastapi import APIRouter, Depends, Header, Response, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.middleware.auth import get_current_user
from app.models import Payment, User
from app.models.constants import PaymentStatus
from app.schemas.booking import PaymentIn, PaymentOut
from app.services import booking_service
from app.utils.errors import AppError

router = APIRouter(prefix="/api/payments", tags=["Payments"])


@router.post("", response_model=PaymentOut, status_code=status.HTTP_201_CREATED)
def pay(data: PaymentIn, response: Response,
        idempotency_key: str = Header(..., alias="Idempotency-Key", min_length=8, max_length=100),
        user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Mock payment. Confirms the booking, books the seats and issues QR tickets - atomically.

    Test card 4000 0000 0000 0002 is declined (402). Re-sending the same Idempotency-Key never charges twice.
    """
    payment, created = booking_service.pay_for_booking(db, user, data, idempotency_key)
    if not created:
        if payment.status == PaymentStatus.FAILED:
            raise AppError(402, payment.failure_reason or "Payment failed")
        response.status_code = status.HTTP_200_OK
    return booking_service.payment_to_out(db, payment)


@router.get("/{payment_id}", response_model=PaymentOut)
def get_payment(payment_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    payment = db.get(Payment, payment_id)
    if payment is None or payment.user_id != user.id:
        raise AppError(404, "Payment not found")
    return booking_service.payment_to_out(db, payment)
