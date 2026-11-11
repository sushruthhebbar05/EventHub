import uuid
from datetime import timedelta

import httpx
import pytest

from app.utils.timeutil import utcnow

pytestmark = pytest.mark.integration


def test_event_creation_generates_seats(organiser, make_event):
    ev = make_event(organiser)
    assert len(ev["seat_ids"]) == 15
    detail = httpx.get(f"{organiser.base_url}/api/events/{ev['id']}").json()
    assert detail["total_seats"] == 15 and detail["available_seats"] == 15 and float(detail["min_price"]) == 500.0
    assert [s["name"] for s in detail["sections"]] == ["Gold", "Silver"]


def test_event_validation(organiser):
    bad = {"title": "x", "category": "Nonsense", "starts_at": (utcnow() - timedelta(days=1)).isoformat(),
           "sections": []}
    assert organiser.http.post("/api/events", json=bad).status_code == 422
    past = {"title": "Past Event", "category": "Concert", "starts_at": (utcnow() - timedelta(days=1)).isoformat(),
            "venue": {"name": "V", "city": "Pune", "address": "x", "capacity": 10},
            "sections": [{"name": "A", "rows": 1, "seats_per_row": 1, "price": 1}]}
    assert organiser.http.post("/api/events", json=past).status_code == 422


def test_pending_events_are_hidden_until_admin_approves(server, organiser, make_event, admin):
    city = f"Hidden-{uuid.uuid4().hex[:6]}"
    ev = make_event(organiser, approve=False, city=city)
    assert ev["status"] == "PENDING"
    public = httpx.get(f"{server}/api/events", params={"city": city}).json()
    assert public["total"] == 0
    assert httpx.get(f"{server}/api/events/{ev['id']}").status_code == 404          # anonymous
    assert organiser.http.get(f"/api/events/{ev['id']}").status_code == 200        # owner can see it
    assert admin.http.post(f"/api/admin/events/{ev['id']}/approve").json()["status"] == "APPROVED"
    assert httpx.get(f"{server}/api/events", params={"city": city}).json()["total"] == 1


def test_search_filters_and_pagination(server, organiser, make_event):
    city = f"Filterburg-{uuid.uuid4().hex[:6]}"
    tag = uuid.uuid4().hex[:8]
    for i in range(5):
        make_event(organiser, city=city, category="Comedy" if i < 3 else "Sports", title=f"Show {tag} number {i}")
    get = lambda **p: httpx.get(f"{server}/api/events", params=p).json()

    assert get(city=city)["total"] == 5
    assert get(city=city.upper())["total"] == 5                       # case-insensitive
    assert get(city=city, category="Comedy")["total"] == 3
    assert get(q=tag.upper())["total"] == 5                           # search by name
    assert get(q=f"{tag} number 4")["total"] == 1
    assert get(city="Nowhere-Land")["total"] == 0

    page1 = get(city=city, page=1, page_size=2)
    page3 = get(city=city, page=3, page_size=2)
    assert (page1["total"], page1["pages"], len(page1["items"])) == (5, 3, 2)
    assert len(page3["items"]) == 1
    ids = {e["id"] for p in (1, 2, 3) for e in get(city=city, page=p, page_size=2)["items"]}
    assert len(ids) == 5                                              # no overlaps or gaps

    day = (utcnow() + timedelta(days=7)).date().isoformat()
    assert get(city=city, date_from=day, date_to=day)["total"] + get(city=city, date_from=(utcnow() + timedelta(days=8)).date().isoformat(), date_to=(utcnow() + timedelta(days=8)).date().isoformat())["total"] == 5
    assert get(city=city, date_from=(utcnow() + timedelta(days=30)).date().isoformat())["total"] == 0


def test_event_card_data_includes_venue_price_and_availability(server, event):
    item = httpx.get(f"{server}/api/events", params={"city": "Testville", "page_size": 50}).json()["items"][0]
    for key in ("title", "starts_at", "venue", "min_price", "category", "image_url", "available_seats"):
        assert key in item
    assert item["venue"]["city"] == "Testville"


def test_update_and_delete_event(organiser, make_event, alice):
    from tests.integration.helpers import buy
    ev = make_event(organiser)
    upd = organiser.http.put(f"/api/events/{ev['id']}", json={"section_prices": {"Gold": "1200"}})
    assert upd.status_code == 200
    assert {s["name"]: float(s["price"]) for s in upd.json()["sections"]}["Gold"] == 1200.0

    deletable = make_event(organiser)
    assert organiser.http.delete(f"/api/events/{deletable['id']}").status_code == 204

    buy(alice, ev["id"], ev["seat_ids"][:1])
    assert organiser.http.delete(f"/api/events/{ev['id']}").status_code == 409     # has bookings
    assert organiser.http.put(f"/api/events/{ev['id']}", json={"cancel": True}).json()["status"] == "CANCELLED"
    assert alice.http.post("/api/holds", json={"event_id": ev["id"], "seat_ids": ev["seat_ids"][1:2]}).status_code == 404


def test_seat_map_shape(server, event):
    m = httpx.get(f"{server}/api/events/{event['id']}/seats").json()
    assert [s["name"] for s in m["sections"]] == ["Gold", "Silver"]
    assert [r["label"] for r in m["sections"][0]["rows"]] == ["A", "B"]
    assert all(seat["status"] == "AVAILABLE" for sec in m["sections"] for row in sec["rows"] for seat in row["seats"])
