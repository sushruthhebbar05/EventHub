import socket
import threading
import time
import uuid
from datetime import timedelta
from pathlib import Path

import httpx
import pytest
import uvicorn
from alembic import command
from alembic.config import Config
from sqlalchemy import text

from app.database import engine
from app.models.constants import Role
from app.utils.security import hash_password
from app.utils.timeutil import utcnow
from tests.integration.helpers import Actor

BACKEND_DIR = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="session")
def server():
    """Create a fresh schema with the real Alembic migrations, then run the real app with uvicorn."""
    with engine.begin() as conn:
        conn.execute(text("DROP SCHEMA public CASCADE"))
        conn.execute(text("CREATE SCHEMA public"))
    command.upgrade(Config(str(BACKEND_DIR / "alembic.ini")), "head")

    from app.main import app

    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]

    class TestServer(uvicorn.Server):
        def install_signal_handlers(self):  # not in the main thread
            pass

    srv = TestServer(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning"))
    thread = threading.Thread(target=srv.run, daemon=True)
    thread.start()
    for _ in range(100):
        if srv.started:
            break
        time.sleep(0.1)
    else:
        raise RuntimeError("test server did not start")
    yield f"http://127.0.0.1:{port}"
    srv.should_exit = True
    thread.join(timeout=10)


@pytest.fixture
def db(server):
    with engine.begin() as conn:
        yield conn


@pytest.fixture
def make_user(server):
    def factory(role: str = "ATTENDEE") -> Actor:
        email = f"{role.lower()}-{uuid.uuid4().hex[:10]}@example.com"
        with httpx.Client(base_url=server) as c:
            if role == Role.ADMIN:  # admins cannot self-register: insert directly
                with engine.begin() as conn:
                    conn.execute(text("INSERT INTO users (name, email, password_hash, role) VALUES (:n, :e, :p, 'ADMIN')"),
                                 {"n": "Test Admin", "e": email, "p": hash_password("Password1")})
                r = c.post("/api/auth/login", json={"email": email, "password": "Password1"})
            else:
                r = c.post("/api/auth/register", json={"name": f"Test {role.title()}", "email": email,
                                                       "password": "Password1", "role": role})
            assert r.status_code in (200, 201), r.text
            body = r.json()
        return Actor(server, body["access_token"], body["user"])
    return factory


@pytest.fixture(scope="session")
def admin(server):
    """One admin for the whole run (admins cannot self-register, so it is inserted directly)."""
    email = f"admin-{uuid.uuid4().hex[:10]}@example.com"
    with engine.begin() as conn:
        conn.execute(text("INSERT INTO users (name, email, password_hash, role) VALUES ('Test Admin', :e, :p, 'ADMIN')"),
                     {"e": email, "p": hash_password("Password1")})
    r = httpx.post(f"{server}/api/auth/login", json={"email": email, "password": "Password1"})
    assert r.status_code == 200, r.text
    return Actor(server, r.json()["access_token"], r.json()["user"])


@pytest.fixture
def organiser(make_user):
    return make_user("ORGANISER")


@pytest.fixture
def alice(make_user):
    return make_user("ATTENDEE")


@pytest.fixture
def bob(make_user):
    return make_user("ATTENDEE")


@pytest.fixture
def make_event(admin):
    """Creates an APPROVED event with 10 Gold seats (2 rows x 5, 1000) + 5 Silver seats (1 row, 500)."""
    def factory(owner: Actor, *, hours_ahead: float = 24 * 7, approve: bool = True, city: str | None = None,
                category: str = "Concert", title: str | None = None) -> dict:
        payload = {
            "title": title or f"Test Event {uuid.uuid4().hex[:6]}", "description": "integration test", "category": category,
            "starts_at": (utcnow() + timedelta(hours=hours_ahead)).isoformat(),
            "venue": {"name": "Test Hall", "city": city or "Testville", "address": "1 Test Road", "capacity": 100},
            "sections": [{"name": "Gold", "rows": 2, "seats_per_row": 5, "price": "1000"},
                         {"name": "Silver", "rows": 1, "seats_per_row": 5, "price": "500"}],
        }
        r = owner.http.post("/api/events", json=payload)
        assert r.status_code == 201, r.text
        event = r.json()
        if approve:
            assert admin.http.post(f"/api/admin/events/{event['id']}/approve").status_code == 200
        with engine.connect() as conn:
            event["seat_ids"] = [r[0] for r in conn.execute(
                text("SELECT id FROM seats WHERE event_id = :e ORDER BY id"), {"e": event["id"]})]
        return event
    return factory


@pytest.fixture
def event(organiser, make_event):
    return make_event(organiser)
