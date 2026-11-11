"""Plain helper functions used by the integration tests."""
import uuid

import httpx


class Actor:
    """A logged-in test user with its own HTTP client."""

    def __init__(self, base_url: str, token: str, user: dict):
        self.base_url, self.token, self.user = base_url, token, user
        self.id, self.email = user["id"], user["email"]
        self.http = self.new_client()

    def new_client(self) -> httpx.Client:
        """A separate client (own connection) - used so threads really hit the server in parallel."""
        return httpx.Client(base_url=self.base_url, timeout=30,
                            headers={"Authorization": f"Bearer {self.token}"})


# ---- small helpers shared by tests -------------------------------------------------
def hold(actor: Actor, event_id: int, seat_ids: list[int]):
    return actor.http.post("/api/holds", json={"event_id": event_id, "seat_ids": seat_ids})


def checkout(actor: Actor, hold_ids: list[int], key: str | None = None):
    return actor.http.post("/api/bookings", json={"hold_ids": hold_ids},
                           headers={"Idempotency-Key": key or uuid.uuid4().hex})


def pay(actor: Actor, booking_id: int, key: str | None = None, card: str = "4242424242424242"):
    return actor.http.post("/api/payments", headers={"Idempotency-Key": key or uuid.uuid4().hex}, json={
        "booking_id": booking_id, "card_number": card, "card_holder": "Test User", "expiry": "12/30", "cvv": "123"})


def buy(actor: Actor, event_id: int, seat_ids: list[int]) -> dict:
    """Full happy path: hold -> checkout -> pay. Returns the confirmed booking."""
    h = hold(actor, event_id, seat_ids)
    assert h.status_code == 201, h.text
    b = checkout(actor, [x["id"] for x in h.json()["holds"]])
    assert b.status_code == 201, b.text
    p = pay(actor, b.json()["id"])
    assert p.status_code == 201, p.text
    return p.json()["booking"]
