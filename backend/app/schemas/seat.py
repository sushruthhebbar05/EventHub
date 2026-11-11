from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field


class SeatOut(BaseModel):
    id: int
    number: int
    status: str  # AVAILABLE | HELD | BOOKED


class RowOut(BaseModel):
    label: str
    seats: list[SeatOut]


class SectionOut(BaseModel):
    name: str
    price: Decimal
    rows: list[RowOut]


class SeatMapOut(BaseModel):
    event_id: int
    sections: list[SectionOut]


class HoldCreate(BaseModel):
    event_id: int
    seat_ids: list[int] = Field(min_length=1, max_length=20)


class HoldOut(BaseModel):
    id: int
    seat_id: int
    event_id: int
    status: str
    expires_at: datetime
    section: str
    row_label: str
    number: int
    price: Decimal


class HoldsOut(BaseModel):
    holds: list[HoldOut]
    expires_at: datetime = Field(description="The earliest expiry among these holds (drive the countdown with this)")
