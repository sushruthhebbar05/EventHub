"""Fills the database with demo users, venues, events (with seats) and a few sample bookings.

    python -m app.seed            # seed only if the database is empty
    python -m app.seed --reset    # wipe all data first, then seed
"""
import random
import secrets
import sys
from datetime import timedelta
from decimal import Decimal
from pathlib import Path

from sqlalchemy import select, text

from app.database import SessionLocal
from app.models import Booking, BookingItem, Event, Hold, Payment, Seat, Ticket, User, Venue
from app.models.constants import (BookingStatus, EventStatus, HoldStatus, ItemStatus, PaymentStatus,
                                  Role, SeatStatus)
from app.schemas.event import EventCreate, SectionIn, VenueIn
from app.services.event_service import create_event
from app.utils.posters import make_poster
from app.utils.security import hash_password
from app.utils.timeutil import utcnow

IMAGES = Path(__file__).resolve().parent / "static" / "images"

DEMO_USERS = [
    ("Asha Admin", "admin@eventhub.dev", "Admin@123", Role.ADMIN),
    ("Omar Organiser", "organiser@eventhub.dev", "Organiser@123", Role.ORGANISER),
    ("Olivia Organiser", "organiser2@eventhub.dev", "Organiser@123", Role.ORGANISER),
    ("Arjun Attendee", "attendee@eventhub.dev", "Attendee@123", Role.ATTENDEE),
    ("Ananya Attendee", "attendee2@eventhub.dev", "Attendee@123", Role.ATTENDEE),
]

VENUES = [
    ("Palace Grounds Arena", "Bengaluru", "Jayamahal Rd, Palace Grounds", 4000),
    ("Bangalore International Centre", "Bengaluru", "Domlur, Bengaluru", 900),
    ("Jio World Convention Centre", "Mumbai", "Bandra Kurla Complex", 3500),
    ("NSCI Dome", "Mumbai", "Worli, Mumbai", 5000),
    ("Jawaharlal Nehru Stadium", "Delhi", "Pragati Vihar, New Delhi", 20000),
    ("HITEX Exhibition Centre", "Hyderabad", "Madhapur, Hyderabad", 6000),
    ("Chennai Trade Centre", "Chennai", "Nandambakkam, Chennai", 4500),
    ("Balewadi Indoor Arena", "Pune", "Balewadi, Pune", 2500),
]

CONCERT = [SectionIn(name="VIP", rows=3, seats_per_row=10, price=Decimal("4500")),
           SectionIn(name="Gold", rows=4, seats_per_row=12, price=Decimal("2500")),
           SectionIn(name="Silver", rows=5, seats_per_row=14, price=Decimal("1200"))]
CONFERENCE = [SectionIn(name="Front Row", rows=2, seats_per_row=10, price=Decimal("3000")),
              SectionIn(name="General", rows=6, seats_per_row=14, price=Decimal("1500"))]
SMALL = [SectionIn(name="Premium", rows=3, seats_per_row=10, price=Decimal("1800")),
         SectionIn(name="Standard", rows=5, seats_per_row=12, price=Decimal("800"))]
SPORTS = [SectionIn(name="Pavilion", rows=3, seats_per_row=14, price=Decimal("3500")),
          SectionIn(name="Stand A", rows=5, seats_per_row=14, price=Decimal("1500")),
          SectionIn(name="Stand B", rows=5, seats_per_row=14, price=Decimal("700"))]

# (title, category, venue index, days from now, hour (UTC), sections, organiser email, description)
EVENTS = [
    ("Neon Nights Live: Arijit Rao", "Concert", 0, 12, 13, CONCERT, "organiser@eventhub.dev",
     "An unforgettable evening of chart-topping hits with a 12-piece live band, lasers and a full light show."),
    ("Bengaluru Indie Fest", "Festival", 0, 28, 10, CONCERT, "organiser@eventhub.dev",
     "Twelve independent bands, food trucks and craft stalls on one lawn. Gates open at 3 PM."),
    ("Mumbai Jazz Evenings", "Concert", 3, 9, 14, CONCERT, "organiser2@eventhub.dev",
     "Smooth jazz under the dome with a rotating line-up of Mumbai's finest players."),
    ("DevSummit India 2026", "Conference", 5, 20, 4, CONFERENCE, "organiser@eventhub.dev",
     "Two tracks on cloud, AI and platform engineering with talks from engineers who run these systems in production."),
    ("Cloud & DevOps Day", "Conference", 1, 35, 4, CONFERENCE, "organiser2@eventhub.dev",
     "A one-day practical conference on containers, CI/CD and observability. Includes lunch."),
    ("AI in Production Summit", "Conference", 2, 52, 4, CONFERENCE, "organiser@eventhub.dev",
     "How teams ship LLM features safely: evaluation, guardrails, cost control and incident stories."),
    ("Laugh Riot: Stand-Up Special", "Comedy", 7, 15, 14, SMALL, "organiser2@eventhub.dev",
     "Four of the country's sharpest comics in one night. Recommended for 16+."),
    ("Hyderabad Comedy Carnival", "Comedy", 5, 40, 13, SMALL, "organiser@eventhub.dev",
     "A double bill of stand-up and improv. Come hungry for laughs."),
    ("Premier Cricket Night Match", "Sports", 4, 24, 13, SPORTS, "organiser@eventhub.dev",
     "Floodlit T20 under the open sky. Gates open two hours before the first ball."),
    ("Chennai Theatre Weekend: Hamlet Reimagined", "Theatre", 6, 18, 12, SMALL, "organiser2@eventhub.dev",
     "A bold, modern staging of the classic with a live string quartet."),
    ("Weekend UX Design Workshop", "Workshop", 7, 8, 4, SMALL, "organiser2@eventhub.dev",
     "Hands-on workshop: research, wireframes and usability testing in a single day."),
    ("Electro Pulse Festival", "Festival", 3, 65, 12, CONCERT, "organiser@eventhub.dev",
     "Eight hours of electronic music across two stages with international headliners."),
]


def wipe(db) -> None:
    db.execute(text("TRUNCATE tickets, payments, booking_items, bookings, holds, seats, events, venues, users RESTART IDENTITY CASCADE"))
    db.commit()


def seed_booking(db, user: User, event: Event, seat_count: int) -> None:
    """Directly writes a confirmed booking (as if the user had paid) so dashboards have data."""
    seats = db.scalars(select(Seat).where(Seat.event_id == event.id, Seat.status == SeatStatus.AVAILABLE)
                       .order_by(Seat.id).offset(random.randint(0, 40)).limit(seat_count)).all()
    if not seats:
        return
    total = sum((s.price for s in seats), Decimal("0"))
    booking = Booking(reference="EH" + secrets.token_hex(4).upper(), user_id=user.id, event_id=event.id,
                      total_amount=total, status=BookingStatus.CONFIRMED, payment_status="PAID",
                      idempotency_key="seed-" + secrets.token_hex(8))
    db.add(booking)
    db.flush()
    for s in seats:
        hold = Hold(user_id=user.id, seat_id=s.id, event_id=event.id, status=HoldStatus.USED,
                    expires_at=utcnow())
        db.add(hold)
        db.flush()
        item = BookingItem(booking_id=booking.id, seat_id=s.id, hold_id=hold.id, price=s.price, status=ItemStatus.CONFIRMED)
        db.add(item)
        db.flush()
        db.add(Ticket(booking_item_id=item.id, code=secrets.token_urlsafe(24)))
        s.status = SeatStatus.BOOKED
    db.add(Payment(booking_id=booking.id, user_id=user.id, amount=total, status=PaymentStatus.SUCCESS,
                   card_last4="4242", provider_ref="mock_" + secrets.token_hex(8),
                   idempotency_key="seed-pay-" + secrets.token_hex(8)))
    db.commit()


def run(reset: bool = False) -> None:
    random.seed(7)
    with SessionLocal() as db:
        if reset:
            wipe(db)
        elif db.scalar(select(User.id).limit(1)):
            print("Database already has data - skipping (use --reset to wipe and re-seed).")
            return

        users = {}
        for name, email, pw, role in DEMO_USERS:
            u = User(name=name, email=email, password_hash=hash_password(pw), role=role)
            db.add(u)
            users[email] = u
        venues = []
        for name, city, address, cap in VENUES:
            v = Venue(name=name, city=city, address=address, capacity=cap)
            db.add(v)
            venues.append(v)
        db.commit()

        events = []
        for i, (title, cat, vi, days, hour, sections, org, desc) in enumerate(EVENTS, start=1):
            poster = IMAGES / f"event-{i}.jpg"
            make_poster(poster, title, cat)
            starts = (utcnow() + timedelta(days=days)).replace(hour=hour, minute=30, second=0, microsecond=0)
            ev = create_event(db, users[org], EventCreate(
                title=title, description=desc, category=cat, image_url=f"/static/images/event-{i}.jpg",
                starts_at=starts, venue_id=venues[vi].id, sections=sections))
            ev.status = EventStatus.APPROVED
            db.commit()
            events.append(ev)

        # one event waiting for approval so the admin screen has something to do
        pend = create_event(db, users["organiser2@eventhub.dev"], EventCreate(
            title="Sunset Acoustic Sessions", description="Intimate acoustic sets on a rooftop.", category="Concert",
            image_url=None, starts_at=utcnow() + timedelta(days=45), venue_id=venues[1].id, sections=SMALL))
        pend.status = EventStatus.PENDING
        make_poster(IMAGES / "pending.jpg", pend.title, "Concert")
        pend.image_url = "/static/images/pending.jpg"
        db.commit()

        for ev, n in zip(events[:6], (9, 14, 7, 11, 5, 3)):
            seed_booking(db, users["attendee2@eventhub.dev"], ev, n)
        print(f"Seeded {len(DEMO_USERS)} users, {len(VENUES)} venues, {len(events) + 1} events.")


if __name__ == "__main__":
    run(reset="--reset" in sys.argv)
