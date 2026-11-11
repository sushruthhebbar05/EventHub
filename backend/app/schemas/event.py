from datetime import datetime, timezone
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

CATEGORIES = ["Concert", "Conference", "Comedy", "Sports", "Theatre", "Festival", "Workshop"]


class VenueIn(BaseModel):
    name: str = Field(min_length=2, max_length=150)
    city: str = Field(min_length=2, max_length=80)
    address: str = Field(min_length=2, max_length=255)
    capacity: int = Field(gt=0, le=200000)


class VenueOut(VenueIn):
    model_config = ConfigDict(from_attributes=True)
    id: int


class SectionIn(BaseModel):
    """Describes one block of seats: `rows` rows (A, B, C...) of `seats_per_row` seats, all at one price."""
    name: str = Field(min_length=1, max_length=30)
    rows: int = Field(ge=1, le=26)
    seats_per_row: int = Field(ge=1, le=40)
    price: Decimal = Field(ge=0, max_digits=10, decimal_places=2)


class EventCreate(BaseModel):
    title: str = Field(min_length=3, max_length=200)
    description: str = Field(default="", max_length=5000)
    category: Literal["Concert", "Conference", "Comedy", "Sports", "Theatre", "Festival", "Workshop"]
    image_url: str | None = Field(default=None, max_length=500)
    starts_at: datetime
    venue_id: int | None = None
    venue: VenueIn | None = None
    sections: list[SectionIn] = Field(min_length=1, max_length=10)

    @field_validator("starts_at")
    @classmethod
    def aware(cls, v: datetime) -> datetime:
        return v if v.tzinfo else v.replace(tzinfo=timezone.utc)

    @model_validator(mode="after")
    def check(self):
        if (self.venue_id is None) == (self.venue is None):
            raise ValueError("Provide exactly one of venue_id or venue")
        names = [s.name.strip().lower() for s in self.sections]
        if len(set(names)) != len(names):
            raise ValueError("Section names must be unique")
        if sum(s.rows * s.seats_per_row for s in self.sections) > 2000:
            raise ValueError("An event can have at most 2000 seats")
        return self


class EventUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=3, max_length=200)
    description: str | None = Field(default=None, max_length=5000)
    category: Literal["Concert", "Conference", "Comedy", "Sports", "Theatre", "Festival", "Workshop"] | None = None
    image_url: str | None = Field(default=None, max_length=500)
    starts_at: datetime | None = None
    cancel: bool | None = Field(default=None, description="Set true to cancel the event")
    section_prices: dict[str, Decimal] | None = Field(
        default=None, description="New price per section name (applies to seats not yet booked)")

    @field_validator("starts_at")
    @classmethod
    def aware(cls, v):
        return v if v is None or v.tzinfo else v.replace(tzinfo=timezone.utc)


class SectionSummary(BaseModel):
    name: str
    price: Decimal
    total: int
    available: int


class EventOut(BaseModel):
    id: int
    title: str
    description: str
    category: str
    image_url: str | None
    starts_at: datetime
    status: str
    organiser_id: int
    venue: VenueOut
    min_price: Decimal | None
    total_seats: int
    available_seats: int


class EventDetail(EventOut):
    sections: list[SectionSummary]


class EventPage(BaseModel):
    items: list[EventOut]
    total: int
    page: int
    page_size: int
    pages: int


class FilterOptions(BaseModel):
    cities: list[str]
    categories: list[str]
