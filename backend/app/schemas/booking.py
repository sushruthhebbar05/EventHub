import re
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field, field_validator


class BookingCreate(BaseModel):
    hold_ids: list[int] = Field(min_length=1, max_length=20)


class TicketBrief(BaseModel):
    id: int
    code: str
    checked_in: bool


class BookingItemOut(BaseModel):
    id: int
    seat_id: int
    section: str
    row_label: str
    number: int
    price: Decimal
    status: str
    ticket: TicketBrief | None = None


class EventBrief(BaseModel):
    id: int
    title: str
    starts_at: datetime
    image_url: str | None
    venue_name: str
    city: str


class BookingOut(BaseModel):
    id: int
    reference: str
    status: str
    payment_status: str
    total_amount: Decimal
    created_at: datetime
    expires_at: datetime | None = Field(default=None, description="For unpaid bookings: when the seat holds run out")
    event: EventBrief
    items: list[BookingItemOut]


class PaymentIn(BaseModel):
    booking_id: int
    card_number: str
    card_holder: str = Field(min_length=2, max_length=80)
    expiry: str = Field(description="MM/YY")
    cvv: str

    @field_validator("card_number")
    @classmethod
    def check_card(cls, v: str) -> str:
        digits = re.sub(r"[\s-]", "", v)
        if not digits.isdigit() or not 13 <= len(digits) <= 19:
            raise ValueError("Card number must be 13-19 digits")
        return digits

    @field_validator("expiry")
    @classmethod
    def check_expiry(cls, v: str) -> str:
        if not re.fullmatch(r"(0[1-9]|1[0-2])/\d{2}", v):
            raise ValueError("Expiry must look like MM/YY")
        return v

    @field_validator("cvv")
    @classmethod
    def check_cvv(cls, v: str) -> str:
        if not re.fullmatch(r"\d{3,4}", v):
            raise ValueError("CVV must be 3 or 4 digits")
        return v


class PaymentOut(BaseModel):
    id: int
    booking_id: int
    amount: Decimal
    status: str
    card_last4: str
    provider_ref: str | None
    created_at: datetime
    booking: BookingOut | None = None


class TicketOut(BaseModel):
    id: int
    code: str
    status: str  # VALID | USED | CANCELLED
    checked_in: bool
    checked_in_at: datetime | None
    section: str
    row_label: str
    number: int
    price: Decimal
    booking_reference: str
    event: EventBrief


class CheckInIn(BaseModel):
    code: str = Field(min_length=8, max_length=64)


class CheckInOut(BaseModel):
    message: str
    ticket: TicketOut
