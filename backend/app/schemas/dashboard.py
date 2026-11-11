from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel


class OrganiserSummary(BaseModel):
    total_events: int
    tickets_sold: int
    total_bookings: int
    total_revenue: Decimal


class EventStats(BaseModel):
    event_id: int
    title: str
    starts_at: datetime
    status: str
    total_seats: int
    booked: int
    held: int
    available: int
    revenue: Decimal


class EventBookingRow(BaseModel):
    booking_id: int
    reference: str
    attendee_name: str
    attendee_email: str
    seats: list[str]
    amount: Decimal
    created_at: datetime
    status: str


class AdminStats(BaseModel):
    users_total: int
    attendees: int
    organisers: int
    admins: int
    events_total: int
    events_pending: int
    events_approved: int
    bookings_confirmed: int
    tickets_sold: int
    revenue: Decimal
