from datetime import timedelta
from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.schemas.booking import PaymentIn
from app.schemas.event import EventCreate, SectionIn, VenueIn
from app.schemas.user import RegisterIn
from app.services.event_service import row_label
from app.utils import payment_gateway
from app.utils.ticket_files import make_qr_png, make_ticket_png
from app.utils.timeutil import utcnow

pytestmark = pytest.mark.unit
PNG = b"\x89PNG\r\n\x1a\n"


def test_register_rejects_weak_password_and_admin_role():
    with pytest.raises(ValidationError):
        RegisterIn(name="Ann", email="ann@example.com", password="onlyletters")
    with pytest.raises(ValidationError):
        RegisterIn(name="Ann", email="ann@example.com", password="Password1", role="ADMIN")
    assert RegisterIn(name="Ann", email="ANN@Example.com", password="Password1").email == "ann@example.com"


def test_payment_card_validation():
    ok = PaymentIn(booking_id=1, card_number="4242 4242 4242 4242", card_holder="Ann", expiry="12/30", cvv="123")
    assert ok.card_number == "4242424242424242"
    for bad in ({"card_number": "abcd"}, {"expiry": "13/30"}, {"cvv": "12"}):
        data = dict(booking_id=1, card_number="4242424242424242", card_holder="Ann", expiry="12/30", cvv="123") | bad
        with pytest.raises(ValidationError):
            PaymentIn(**data)


def _event(**kw):
    base = dict(title="Test Event", category="Concert", starts_at=utcnow() + timedelta(days=3),
                venue_id=1, sections=[SectionIn(name="A", rows=2, seats_per_row=5, price=Decimal("10"))])
    return EventCreate(**(base | kw))


def test_event_needs_exactly_one_of_venue_or_venue_id():
    _event()
    with pytest.raises(ValidationError):
        _event(venue_id=None)
    with pytest.raises(ValidationError):
        _event(venue=VenueIn(name="V", city="Pune", address="x", capacity=10))


def test_event_rejects_duplicate_sections_and_huge_layouts():
    with pytest.raises(ValidationError):
        _event(sections=[SectionIn(name="A", rows=1, seats_per_row=1, price=1),
                         SectionIn(name="a", rows=1, seats_per_row=1, price=1)])
    with pytest.raises(ValidationError):
        _event(sections=[SectionIn(name=f"S{i}", rows=26, seats_per_row=40, price=1) for i in range(3)])


def test_row_labels():
    assert [row_label(i) for i in (0, 1, 25)] == ["A", "B", "Z"]


def test_mock_gateway():
    assert payment_gateway.charge("4242424242424242", 10).approved
    declined = payment_gateway.charge("4000000000000002", 10)
    assert not declined.approved and declined.failure_reason


def test_qr_and_ticket_images_are_pngs():
    assert make_qr_png("some-random-code").startswith(PNG)
    png = make_ticket_png(event_title="Show", when="Mon", venue="Hall", seat="A1", reference="EH1", code="abc")
    assert png.startswith(PNG)
