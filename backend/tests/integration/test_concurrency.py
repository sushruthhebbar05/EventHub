"""THE MANDATORY TEST: two (or many) users race for the same seat against a REAL PostgreSQL database.

Each thread has its own HTTP client / TCP connection, and a Barrier releases all threads at the same instant, so the
requests reach the running FastAPI server (and therefore PostgreSQL) concurrently. There are no mocks.
"""
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor

import pytest
from sqlalchemy import text

from tests.integration.helpers import Actor

pytestmark = pytest.mark.integration


def race(actors: list[Actor], fn):
    """Run fn(actor, client) in one thread per actor, all released at the same moment."""
    barrier = threading.Barrier(len(actors))

    def worker(actor: Actor):
        client = actor.new_client()
        try:
            barrier.wait(timeout=10)
            return fn(actor, client)
        finally:
            client.close()

    with ThreadPoolExecutor(max_workers=len(actors)) as pool:
        return list(pool.map(worker, actors))


def full_flow(event_id: int, seat_ids: list[int]):
    """hold -> checkout -> pay, returning the HTTP status of the first step that fails (or 201 on success)."""
    def run(actor: Actor, c):
        r = c.post("/api/holds", json={"event_id": event_id, "seat_ids": seat_ids})
        if r.status_code != 201:
            return r.status_code
        ids = [h["id"] for h in r.json()["holds"]]
        r = c.post("/api/bookings", json={"hold_ids": ids}, headers={"Idempotency-Key": uuid.uuid4().hex})
        if r.status_code != 201:
            return r.status_code
        r = c.post("/api/payments", headers={"Idempotency-Key": uuid.uuid4().hex}, json={
            "booking_id": r.json()["id"], "card_number": "4242424242424242", "card_holder": "Racer",
            "expiry": "12/30", "cvv": "123"})
        return r.status_code
    return run


def confirmed_items(db, seat_id) -> int:
    return db.execute(text("SELECT count(*) FROM booking_items WHERE seat_id=:s AND status='CONFIRMED'"),
                      {"s": seat_id}).scalar_one()


def test_two_users_cannot_book_the_same_seat(db, alice, bob, event):
    """User A and User B go for the same seat at the same instant: exactly one wins, the other gets 409."""
    seat = event["seat_ids"][0]
    results = race([alice, bob], lambda a, c: c.post("/api/holds", json={"event_id": event["id"], "seat_ids": [seat]}).status_code)
    assert sorted(results) == [201, 409]
    assert db.execute(text("SELECT count(*) FROM holds WHERE seat_id=:s AND status='ACTIVE'"), {"s": seat}).scalar_one() == 1


def test_two_users_race_through_the_whole_booking_flow_and_only_one_booking_is_confirmed(db, alice, bob, event):
    seat = event["seat_ids"][1]
    results = race([alice, bob], full_flow(event["id"], [seat]))
    assert sorted(results) == [201, 409]                     # one confirmed, one told "409 Conflict"
    assert confirmed_items(db, seat) == 1                    # only one confirmed booking exists in the database
    assert db.execute(text("SELECT status FROM seats WHERE id=:s"), {"s": seat}).scalar_one() == "BOOKED"
    assert db.execute(text("""SELECT count(*) FROM tickets t JOIN booking_items i ON i.id=t.booking_item_id
                              WHERE i.seat_id=:s"""), {"s": seat}).scalar_one() == 1


def test_many_users_one_seat_exactly_one_winner(db, make_user, event):
    users = [make_user() for _ in range(12)]
    seat = event["seat_ids"][2]
    results = race(users, full_flow(event["id"], [seat]))
    assert results.count(201) == 1 and results.count(409) == 11, results
    assert confirmed_items(db, seat) == 1


def test_overlapping_multi_seat_requests_do_not_deadlock(db, alice, bob, event):
    """A wants seats 1+2, B wants seats 2+1 (reverse order). Locks are taken in id order, so no deadlock."""
    s1, s2 = event["seat_ids"][3:5]
    outcomes = {}

    def run(actor, c):
        seats = [s1, s2] if actor is alice else [s2, s1]
        outcomes[actor.id] = c.post("/api/holds", json={"event_id": event["id"], "seat_ids": seats}).status_code
        return outcomes[actor.id]

    assert sorted(race([alice, bob], run)) == [201, 409]
    holders = {r[0] for r in db.execute(text("SELECT user_id FROM holds WHERE seat_id IN (:a,:b) AND status='ACTIVE'"), {"a": s1, "b": s2})}
    assert len(holders) == 1                                  # both seats belong to the single winner


def test_disjoint_seats_do_not_block_each_other(alice, bob, event):
    s = event["seat_ids"]
    results = race([alice, bob], lambda a, c: c.post("/api/holds", json={
        "event_id": event["id"], "seat_ids": [s[5]] if a is alice else [s[6]]}).status_code)
    assert results == [201, 201]


def test_paying_the_same_booking_twice_at_once_confirms_only_once(db, alice, event):
    """Two payment requests with DIFFERENT idempotency keys race for the same booking."""
    from tests.integration.helpers import checkout, hold
    h = hold(alice, event["id"], event["seat_ids"][7:9]).json()
    booking = checkout(alice, [x["id"] for x in h["holds"]]).json()

    def run(actor, c):
        return c.post("/api/payments", headers={"Idempotency-Key": uuid.uuid4().hex}, json={
            "booking_id": booking["id"], "card_number": "4242424242424242", "card_holder": "Twin",
            "expiry": "12/30", "cvv": "123"}).status_code

    results = race([alice, alice, alice], run)
    assert results.count(201) == 1 and results.count(409) == 2, results
    assert db.execute(text("SELECT count(*) FROM payments WHERE booking_id=:b AND status='SUCCESS'"), {"b": booking["id"]}).scalar_one() == 1
    assert db.execute(text("SELECT count(*) FROM tickets t JOIN booking_items i ON i.id=t.booking_item_id WHERE i.booking_id=:b"),
                      {"b": booking["id"]}).scalar_one() == 2


def test_identical_checkout_requests_at_once_create_one_booking(db, alice, event):
    from tests.integration.helpers import hold
    h = hold(alice, event["id"], event["seat_ids"][9:10]).json()
    ids, key = [x["id"] for x in h["holds"]], uuid.uuid4().hex
    results = race([alice] * 4, lambda a, c: c.post("/api/bookings", json={"hold_ids": ids}, headers={"Idempotency-Key": key}).json()["id"])
    assert len(set(results)) == 1
    assert db.execute(text("SELECT count(*) FROM bookings WHERE idempotency_key=:k"), {"k": key}).scalar_one() == 1
