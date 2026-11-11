import uuid
from datetime import timedelta

import httpx
import pytest
from jose import jwt

from app.config import settings
from app.utils.timeutil import utcnow
from tests.integration.helpers import hold

pytestmark = pytest.mark.integration


def test_register_login_and_me(server):
    email = f"reg-{uuid.uuid4().hex[:8]}@example.com"
    with httpx.Client(base_url=server) as c:
        r = c.post("/api/auth/register", json={"name": "Reg User", "email": email, "password": "Password1"})
        assert r.status_code == 201
        assert r.json()["user"]["role"] == "ATTENDEE"
        assert "password" not in r.text and "hash" not in r.text

        assert c.post("/api/auth/register", json={"name": "Dup", "email": email.upper(), "password": "Password1"}).status_code == 409

        login = c.post("/api/auth/login", json={"email": email, "password": "Password1"})
        assert login.status_code == 200
        me = c.get("/api/auth/me", headers={"Authorization": f"Bearer {login.json()['access_token']}"})
        assert me.status_code == 200 and me.json()["email"] == email


def test_login_failures_use_same_message(server):
    with httpx.Client(base_url=server) as c:
        wrong_pw = c.post("/api/auth/login", json={"email": "nobody@example.com", "password": "Password1"})
        assert wrong_pw.status_code == 401


def test_cannot_register_as_admin_or_with_weak_password(server):
    with httpx.Client(base_url=server) as c:
        base = {"name": "Evil", "email": f"e-{uuid.uuid4().hex[:6]}@example.com"}
        assert c.post("/api/auth/register", json=base | {"password": "Password1", "role": "ADMIN"}).status_code == 422
        assert c.post("/api/auth/register", json=base | {"password": "short1"}).status_code == 422
        assert c.post("/api/auth/register", json=base | {"password": "nodigitshere"}).status_code == 422


@pytest.mark.parametrize("header", [None, "Bearer garbage", "Bearer a.b.c", "Basic abc"])
def test_invalid_or_missing_jwt_is_401(server, header):
    headers = {"Authorization": header} if header else {}
    r = httpx.get(f"{server}/api/auth/me", headers=headers)
    assert r.status_code == 401


def test_expired_and_forged_jwt_rejected(server, alice):
    expired = jwt.encode({"sub": str(alice.id), "exp": utcnow() - timedelta(minutes=1)}, settings.jwt_secret, algorithm="HS256")
    forged = jwt.encode({"sub": str(alice.id), "exp": utcnow() + timedelta(minutes=5)}, "wrong-secret", algorithm="HS256")
    for token in (expired, forged):
        assert httpx.get(f"{server}/api/auth/me", headers={"Authorization": f"Bearer {token}"}).status_code == 401


def test_protected_endpoints_need_login(server, event):
    with httpx.Client(base_url=server) as c:
        assert c.post("/api/holds", json={"event_id": event["id"], "seat_ids": [event["seat_ids"][0]]}).status_code == 401
        assert c.get("/api/bookings").status_code == 401
        assert c.get("/api/tickets").status_code == 401


def test_attendee_cannot_use_organiser_or_admin_apis(alice, event):
    payload = {"title": "Nope Event", "category": "Concert", "starts_at": (utcnow() + timedelta(days=2)).isoformat(),
               "venue_id": 1, "sections": [{"name": "A", "rows": 1, "seats_per_row": 1, "price": 1}]}
    assert alice.http.post("/api/events", json=payload).status_code == 403
    assert alice.http.get("/api/organiser/summary").status_code == 403
    assert alice.http.get("/api/organiser/events/stats").status_code == 403
    assert alice.http.post("/api/tickets/check-in", json={"code": "x" * 20}).status_code == 403
    assert alice.http.get("/api/admin/stats").status_code == 403
    assert alice.http.post(f"/api/admin/events/{event['id']}/approve").status_code == 403
    assert alice.http.patch("/api/admin/users/1", json={"role": "ADMIN"}).status_code == 403


def test_organiser_cannot_use_admin_apis(organiser):
    assert organiser.http.get("/api/admin/users").status_code == 403
    assert organiser.http.get("/api/admin/stats").status_code == 403


def test_organiser_can_only_manage_own_events(make_user, organiser, event):
    other = make_user("ORGANISER")
    assert other.http.put(f"/api/events/{event['id']}", json={"title": "Hijacked"}).status_code == 403
    assert other.http.delete(f"/api/events/{event['id']}").status_code == 403
    assert other.http.get(f"/api/organiser/events/{event['id']}/bookings").status_code == 403
    # the owner can
    assert organiser.http.put(f"/api/events/{event['id']}", json={"title": "My New Title"}).json()["title"] == "My New Title"


def test_organiser_dashboard_is_scoped_to_own_events(make_user, make_event, alice):
    from tests.integration.helpers import buy
    org_a, org_b = make_user("ORGANISER"), make_user("ORGANISER")
    ev_a, ev_b = make_event(org_a), make_event(org_b)
    buy(alice, ev_a["id"], ev_a["seat_ids"][:2])          # 2 Gold seats = 2000
    a = org_a.http.get("/api/organiser/summary").json()
    b = org_b.http.get("/api/organiser/summary").json()
    assert (a["total_events"], a["tickets_sold"], float(a["total_revenue"])) == (1, 2, 2000.0)
    assert (b["total_events"], b["tickets_sold"], float(b["total_revenue"])) == (1, 0, 0.0)
    stats_a = org_a.http.get("/api/organiser/events/stats").json()
    assert [s["event_id"] for s in stats_a] == [ev_a["id"]] and stats_a[0]["booked"] == 2 and stats_a[0]["available"] == 13


def test_admin_can_manage_users(admin, alice):
    r = admin.http.patch(f"/api/admin/users/{alice.id}", json={"is_active": False})
    assert r.status_code == 200 and r.json()["is_active"] is False
    assert alice.http.get("/api/auth/me").status_code == 401            # disabled accounts lose access at once
    assert admin.http.patch(f"/api/admin/users/{admin.id}", json={"role": "ATTENDEE"}).status_code == 409
