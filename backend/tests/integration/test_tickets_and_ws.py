import json

import httpx
import pytest
from websockets.sync.client import connect

from tests.integration.helpers import buy, hold

pytestmark = pytest.mark.integration
PNG = b"\x89PNG\r\n\x1a\n"


def test_ticket_has_unique_unguessable_code_and_qr(alice, event):
    booking = buy(alice, event["id"], event["seat_ids"][:3])
    codes = [i["ticket"]["code"] for i in booking["items"]]
    assert len(set(codes)) == 3 and all(len(c) >= 30 for c in codes)
    for forbidden in (alice.email, alice.user["name"]):
        assert all(forbidden not in c for c in codes)                  # no personal data inside the code

    tickets = alice.http.get("/api/tickets").json()
    assert {t["code"] for t in tickets} == set(codes)
    tid = tickets[0]["id"]
    qr = alice.http.get(f"/api/tickets/{tid}/qr")
    assert qr.status_code == 200 and qr.headers["content-type"] == "image/png" and qr.content.startswith(PNG)
    dl = alice.http.get(f"/api/tickets/{tid}/download")
    assert dl.status_code == 200 and dl.content.startswith(PNG) and "attachment" in dl.headers["content-disposition"]


def test_ticket_is_private_to_its_owner(alice, bob, event):
    buy(alice, event["id"], event["seat_ids"][:1])
    tid = alice.http.get("/api/tickets").json()[0]["id"]
    for path in (f"/api/tickets/{tid}", f"/api/tickets/{tid}/qr", f"/api/tickets/{tid}/download"):
        assert bob.http.get(path).status_code == 404
    assert bob.http.get("/api/tickets").json() == []


def test_entry_check_in_accepts_once_and_rejects_duplicates(alice, organiser, make_user, event):
    booking = buy(alice, event["id"], event["seat_ids"][:1])
    code = booking["items"][0]["ticket"]["code"]
    other_organiser = make_user("ORGANISER")

    assert other_organiser.http.post("/api/tickets/check-in", json={"code": code}).status_code == 403
    assert organiser.http.post("/api/tickets/check-in", json={"code": "does-not-exist-12345"}).status_code == 404
    first = organiser.http.post("/api/tickets/check-in", json={"code": code})
    assert first.status_code == 200 and first.json()["ticket"]["status"] == "USED"
    second = organiser.http.post("/api/tickets/check-in", json={"code": code})
    assert second.status_code == 409 and "already" in second.json()["detail"]


def test_organiser_sees_booking_details_for_their_event(alice, organiser, event):
    buy(alice, event["id"], event["seat_ids"][:2])
    rows = organiser.http.get(f"/api/organiser/events/{event['id']}/bookings").json()
    assert len(rows) == 1 and rows[0]["attendee_email"] == alice.email and len(rows[0]["seats"]) == 2


# ------------------------------------------------------------------ websocket
def ws_url(base: str, event_id: int) -> str:
    return base.replace("http://", "ws://") + f"/ws/events/{event_id}"


def next_update(ws, timeout=5):
    while True:
        msg = json.loads(ws.recv(timeout=timeout))
        if msg.get("type") == "seat_update":
            return msg


def test_websocket_pushes_hold_release_and_booking_updates(server, alice, bob, event):
    seat = event["seat_ids"][0]
    with connect(ws_url(server, event["id"])) as ws:
        assert json.loads(ws.recv(timeout=5))["type"] == "connected"

        hid = hold(alice, event["id"], [seat]).json()["holds"][0]["id"]
        assert next_update(ws)["seats"] == [{"seat_id": seat, "status": "HELD"}]

        alice.http.delete(f"/api/holds/{hid}")
        assert next_update(ws)["seats"] == [{"seat_id": seat, "status": "AVAILABLE"}]

        buy(bob, event["id"], [seat])
        statuses = [next_update(ws)["seats"][0]["status"], next_update(ws)["seats"][0]["status"]]
        assert statuses == ["HELD", "BOOKED"]


def test_websocket_only_receives_updates_for_its_own_event(server, alice, organiser, make_event, event):
    other = make_event(organiser)
    with connect(ws_url(server, other["id"])) as ws:
        ws.recv(timeout=5)
        hold(alice, event["id"], [event["seat_ids"][0]])
        with pytest.raises(TimeoutError):
            ws.recv(timeout=1.0)


def test_websocket_ping_and_clean_disconnect(server, alice, event):
    ws = connect(ws_url(server, event["id"]))
    ws.recv(timeout=5)
    ws.send("ping")
    assert ws.recv(timeout=5) == "pong"
    ws.close()
    # the server must survive a dropped client and keep broadcasting
    with connect(ws_url(server, event["id"])) as ws2:
        ws2.recv(timeout=5)
        hold(alice, event["id"], [event["seat_ids"][1]])
        assert next_update(ws2)["seats"][0]["status"] == "HELD"
