from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.middleware.auth import get_current_user
from app.models import User
from app.schemas.seat import HoldCreate, HoldOut, HoldsOut
from app.services import seat_service

router = APIRouter(prefix="/api/holds", tags=["Holds"])


@router.post("", response_model=HoldsOut, status_code=status.HTTP_201_CREATED)
def hold_seats(data: HoldCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Temporarily hold seats for 5 minutes. Returns 409 if any seat is already held by someone else or booked."""
    holds = seat_service.create_holds(db, user, data.event_id, data.seat_ids)
    return HoldsOut(holds=holds, expires_at=min(h.expires_at for h in holds))


@router.get("/mine", response_model=list[HoldOut])
def my_holds(event_id: int | None = Query(None), user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Your currently active holds (used to restore the selection after a page refresh)."""
    return seat_service.my_active_holds(db, user, event_id)


@router.delete("/{hold_id}", status_code=status.HTTP_204_NO_CONTENT)
def release_hold(hold_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Give a held seat back (deselect)."""
    seat_service.release_hold(db, user, hold_id)
