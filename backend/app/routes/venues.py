from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.middleware.auth import require_organiser
from app.models import User, Venue
from app.schemas.event import VenueIn, VenueOut
from app.utils.errors import AppError

router = APIRouter(prefix="/api/venues", tags=["Venues"])


@router.get("", response_model=list[VenueOut])
def list_venues(city: str | None = None, db: Session = Depends(get_db)):
    stmt = select(Venue).order_by(Venue.city, Venue.name)
    if city:
        stmt = stmt.where(Venue.city.ilike(city))
    return db.scalars(stmt).all()


@router.get("/{venue_id}", response_model=VenueOut)
def get_venue(venue_id: int, db: Session = Depends(get_db)):
    venue = db.get(Venue, venue_id)
    if venue is None:
        raise AppError(404, "Venue not found")
    return venue


@router.post("", response_model=VenueOut, status_code=status.HTTP_201_CREATED)
def create_venue(data: VenueIn, _: User = Depends(require_organiser), db: Session = Depends(get_db)):
    venue = Venue(**data.model_dump())
    db.add(venue)
    db.commit()
    return venue
