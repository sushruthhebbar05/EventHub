import time
import uuid

import pytest
from sqlalchemy import text

from tests.integration.helpers import buy, checkout, hold, pay

pytestmark = pytest.mark.integration


def seat_status(db, seat_id):
    return db.execute(text("SELECT status FROM seats WHERE id = :i"), {"i": seat_id}).scalar_one()


# ------------------------------------------------------------------ holds
def test_hold_creates_five_minute_hold_and_marks_seat_held(db, alice, event):
    seat = event["seat_ids"][0]
    r = hold(alice, event["id"], [seat])
    assert r.status_code == 201
    body = r.json()
    h = body["holds"][0]
    assert h["seat_id"] == seat and h["status"] == "ACTIVE" and h["id"]
    secs = db.execute(text("SELECT EXTRACT(EPOCH FROM (expires_at - now())) FROM holds WHERE id=:i"), {"i": h["id"]}).scalar_one()
    assert 290 < secs <= 300
    assert seat_status(db, seat) == "HELD"
    mine = alice.http.get("/api/holds/mine", params={"event_id": event["id"]}).json()
    assert [m["id"] for m in mine] == [h["id"]]


def test_seat_held_by_someone_else_returns_409(alice, bob, event):
    seat = event["seat_ids"][0]
    assert hold(alice, event["id"], [seat]).status_code == 201
    r = hold(bob, event["id"], [seat])
    assert r.status_code == 409 and r.json()["seat_ids"] == [seat]


def test_holding_your_own_seat_again_is_idempotent(db, alice, event):
    seat = event["seat_ids"][0]
    first = hold(alice, event["id"], [seat]).json()["holds"][0]["id"]
    assert hold(alice, event["id"], [seat]).json()["holds"][0]["id"] == first
    assert db.execute(text("SELECT count(*) FROM holds WHERE seat_id=:s AND status='ACTIVE'"), {"s": seat}).scalar_one() == 1


def test_multi_seat_hold_is_all_or_nothing(db, alice, bob, event):
    s1, s2 = event["seat_ids"][:2]
    assert hold(alice, event["id"], [s2]).status_code == 201
    assert hold(bob, event["id"], [s1, s2]).status_code == 409
    assert seat_status(db, s1) == "AVAILABLE"       # s1 was NOT grabbed by the failed request


def test_hold_limits_and_bad_input(alice, event):
    assert hold(alice, event["id"], event["seat_ids"][:7]).status_code == 422                # > 6 seats
    assert hold(alice, event["id"], [999999999]).status_code == 404                           # unknown seat
    assert hold(alice, 999999999, [event["seat_ids"][0]]).status_code == 404                 # unknown event
    assert alice.http.post("/api/holds", json={"event_id": event["id"], "seat_ids": []}).status_code == 422


def test_release_hold_frees_seat_and_only_owner_can_release(db, alice, bob, event):
    seat = event["seat_ids"][0]
    hid = hold(alice, event["id"], [seat]).json()["holds"][0]["id"]
    assert bob.http.delete(f"/api/holds/{hid}").status_code == 404
    assert alice.http.delete(f"/api/holds/{hid}").status_code == 204
    assert seat_status(db, seat) == "AVAILABLE"
    assert hold(bob, event["id"], [seat]).status_code == 201


# ------------------------------------------------------------------ expiry
def test_hold_expiry_end_to_end(server, alice, bob, event):
    """Expire a hold by editing its expiry in PostgreSQL; the sweeper must free the seat within a few seconds."""
    from app.database import engine
    seat = event["seat_ids"][0]
    hid = hold(alice, event["id"], [seat]).json()["holds"][0]["id"]
    with engine.begin() as conn:
        conn.execute(text("UPDATE holds SET expires_at = now() - interval '2 seconds' WHERE id = :i"), {"i": hid})
    deadline = time.time() + 8
    status = None
    while time.time() < deadline:
        with engine.connect() as conn:
            status = conn.execute(text("SELECT status FROM seats WHERE id=:s"), {"s": seat}).scalar_one()
            hold_status = conn.execute(text("SELECT status FROM holds WHERE id=:i"), {"i": hid}).scalar_one()
        if status == "AVAILABLE":
            break
        time.sleep(0.3)
    assert status == "AVAILABLE" and hold_status == "EXPIRED"
    assert hold(bob, event["id"], [seat]).status_code == 201          # someone else can now take it


def test_expired_hold_does_not_block_other_users_even_before_the_sweeper_runs(alice, bob, event):
    from app.database import engine
    seat = event["seat_ids"][1]
    hid = hold(alice, event["id"], [seat]).json()["holds"][0]["id"]
    with engine.begin() as conn:
        conn.execute(text("UPDATE holds SET expires_at = now() - interval '1 second' WHERE id = :i"), {"i": hid})
    assert hold(bob, event["id"], [seat]).status_code == 201


def test_cannot_pay_with_an_expired_hold(alice, event):
    from app.database import engine
    seat = event["seat_ids"][2]
    h = hold(alice, event["id"], [seat]).json()["holds"][0]
    booking = checkout(alice, [h["id"]]).json()
    with engine.begin() as conn:
        conn.execute(text("UPDATE holds SET expires_at = now() - interval '1 second' WHERE id = :i"), {"i": h["id"]})
    r = pay(alice, booking["id"])
    assert r.status_code == 410
    after = alice.http.get(f"/api/bookings/{booking['id']}").json()
    assert after["status"] == "EXPIRED" and all(i["ticket"] is None for i in after["items"])
    with engine.connect() as conn:
        assert conn.execute(text("SELECT status FROM seats WHERE id=:s"), {"s": seat}).scalar_one() == "AVAILABLE"
        assert conn.execute(text("SELECT count(*) FROM payments WHERE booking_id=:b"), {"b": booking["id"]}).scalar_one() == 0


def test_cannot_start_checkout_with_expired_hold(alice, event):
    from app.database import engine
    h = hold(alice, event["id"], [event["seat_ids"][3]]).json()["holds"][0]
    with engine.begin() as conn:
        conn.execute(text("UPDATE holds SET expires_at = now() - interval '1 second' WHERE id = :i"), {"i": h["id"]})
    assert checkout(alice, [h["id"]]).status_code == 410


# ------------------------------------------------------------------ booking, payment, tickets
def test_full_booking_flow_creates_confirmed_booking_and_tickets(db, alice, event):
    seats = event["seat_ids"][:2] + event["seat_ids"][-1:]          # 2 Gold (1000) + 1 Silver (500)
    h = hold(alice, event["id"], seats).json()
    b = checkout(alice, [x["id"] for x in h["holds"]])
    assert b.status_code == 201
    bj = b.json()
    assert bj["status"] == "PENDING_PAYMENT" and float(bj["total_amount"]) == 2500.0 and bj["expires_at"]

    p = pay(alice, bj["id"])
    assert p.status_code == 201
    booking = p.json()["booking"]
    assert booking["status"] == "CONFIRMED" and booking["payment_status"] == "PAID"
    assert len(booking["items"]) == 3 and all(i["ticket"] and i["status"] == "CONFIRMED" for i in booking["items"])
    assert p.json()["card_last4"] == "4242"
    for s in seats:
        assert seat_status(db, s) == "BOOKED"
    assert db.execute(text("SELECT count(*) FROM tickets t JOIN booking_items i ON i.id=t.booking_item_id WHERE i.booking_id=:b"),
                      {"b": bj["id"]}).scalar_one() == 3

    history = alice.http.get("/api/bookings").json()
    assert bj["id"] in [x["id"] for x in history]
    assert alice.http.get(f"/api/bookings/{bj['id']}").status_code == 200


def test_booked_seat_cannot_be_held_again(alice, bob, event):
    seat = event["seat_ids"][0]
    buy(alice, event["id"], [seat])
    r = hold(bob, event["id"], [seat])
    assert r.status_code == 409 and r.json()["seat_ids"] == [seat]
    assert bob.http.get(f"/api/events/{event['id']}/seats").json()["sections"][0]["rows"][0]["seats"][0]["status"] == "BOOKED"


def test_cannot_book_someone_elses_hold(alice, bob, event):
    h = hold(alice, event["id"], [event["seat_ids"][0]]).json()["holds"][0]
    assert checkout(bob, [h["id"]]).status_code == 404


def test_duplicate_booking_request_with_same_idempotency_key_returns_same_booking(db, alice, event):
    h = hold(alice, event["id"], event["seat_ids"][:2]).json()
    ids = [x["id"] for x in h["holds"]]
    key = uuid.uuid4().hex
    first, second = checkout(alice, ids, key), checkout(alice, ids, key)
    assert (first.status_code, second.status_code) == (201, 200)
    assert first.json()["id"] == second.json()["id"]
    assert db.execute(text("SELECT count(*) FROM bookings WHERE user_id=:u"), {"u": alice.id}).scalar_one() == 1


def test_same_holds_with_a_different_key_cannot_create_a_second_booking(alice, event):
    ids = [x["id"] for x in hold(alice, event["id"], event["seat_ids"][:1]).json()["holds"]]
    assert checkout(alice, ids).status_code == 201
    assert checkout(alice, ids).status_code == 409


def test_idempotency_key_is_required(alice, event):
    ids = [x["id"] for x in hold(alice, event["id"], event["seat_ids"][:1]).json()["holds"]]
    assert alice.http.post("/api/bookings", json={"hold_ids": ids}).status_code == 422


def test_duplicate_payment_attempts_never_charge_twice(db, alice, event):
    h = hold(alice, event["id"], event["seat_ids"][:2]).json()
    b = checkout(alice, [x["id"] for x in h["holds"]]).json()
    key = uuid.uuid4().hex
    first, replay = pay(alice, b["id"], key), pay(alice, b["id"], key)
    assert (first.status_code, replay.status_code) == (201, 200)
    assert first.json()["id"] == replay.json()["id"]
    # a *new* key for an already-paid booking is rejected
    assert pay(alice, b["id"]).status_code == 409
    assert db.execute(text("SELECT count(*) FROM payments WHERE booking_id=:b AND status='SUCCESS'"), {"b": b["id"]}).scalar_one() == 1
    assert db.execute(text("SELECT count(*) FROM tickets t JOIN booking_items i ON i.id=t.booking_item_id WHERE i.booking_id=:b"),
                      {"b": b["id"]}).scalar_one() == 2


def test_declined_card_keeps_hold_so_user_can_retry(db, alice, event):
    seat = event["seat_ids"][0]
    h = hold(alice, event["id"], [seat]).json()
    b = checkout(alice, [x["id"] for x in h["holds"]]).json()
    key = uuid.uuid4().hex
    assert pay(alice, b["id"], key, card="4000000000000002").status_code == 402
    assert pay(alice, b["id"], key, card="4000000000000002").status_code == 402     # replay of the failed attempt
    assert seat_status(db, seat) == "HELD"
    ok = pay(alice, b["id"])                                                         # new key, valid card
    assert ok.status_code == 201 and ok.json()["booking"]["status"] == "CONFIRMED"


def test_other_users_cannot_pay_for_or_view_my_booking(alice, bob, event):
    h = hold(alice, event["id"], event["seat_ids"][:1]).json()
    b = checkout(alice, [x["id"] for x in h["holds"]]).json()
    assert pay(bob, b["id"]).status_code == 404
    assert bob.http.get(f"/api/bookings/{b['id']}").status_code == 404
    assert bob.http.post(f"/api/bookings/{b['id']}/cancel").status_code == 404


def test_cancel_pending_checkout_releases_seats(db, alice, bob, event):
    seat = event["seat_ids"][0]
    h = hold(alice, event["id"], [seat]).json()
    b = checkout(alice, [x["id"] for x in h["holds"]]).json()
    assert alice.http.delete(f"/api/holds/{h['holds'][0]['id']}").status_code == 409   # part of a checkout
    assert alice.http.post(f"/api/bookings/{b['id']}/cancel").json()["status"] == "CANCELLED"
    assert seat_status(db, seat) == "AVAILABLE"
    assert hold(bob, event["id"], [seat]).status_code == 201


def test_cancel_confirmed_booking_refunds_and_frees_seats(db, alice, event):
    seat = event["seat_ids"][0]
    booking = buy(alice, event["id"], [seat])
    r = alice.http.post(f"/api/bookings/{booking['id']}/cancel")
    assert r.status_code == 200 and r.json()["status"] == "CANCELLED" and r.json()["payment_status"] == "REFUNDED"
    assert seat_status(db, seat) == "AVAILABLE"
    assert alice.http.get("/api/tickets").json()[0]["status"] == "CANCELLED"
    assert alice.http.post(f"/api/bookings/{booking['id']}/cancel").status_code == 409     # cannot cancel twice


def test_cannot_cancel_inside_the_cutoff_window(organiser, alice, make_event):
    soon = make_event(organiser, hours_ahead=2)
    booking = buy(alice, soon["id"], soon["seat_ids"][:1])
    assert alice.http.post(f"/api/bookings/{booking['id']}/cancel").status_code == 409


def test_database_constraints_block_double_booking_even_without_python(db, alice, event):
    """Defence in depth: bypass the app and try to confirm a second booking item on a booked seat."""
    from sqlalchemy.exc import IntegrityError
    seat = event["seat_ids"][0]
    buy(alice, event["id"], [seat])
    with pytest.raises(IntegrityError):
        db.execute(text("""INSERT INTO booking_items (booking_id, seat_id, hold_id, price, status)
                           SELECT booking_id, seat_id, (SELECT max(id)+1000 FROM holds), price, 'CONFIRMED'
                           FROM booking_items WHERE seat_id = :s"""), {"s": seat})
