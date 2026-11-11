"""Shared test setup.

Integration tests use a REAL PostgreSQL database (never SQLite, never mocks) because the whole point is to
prove that PostgreSQL row locking prevents double booking.

The test database is wiped on every run, so we refuse to run unless its name ends with "_test".
"""
import os

os.environ["DATABASE_URL"] = os.environ.get(
    "TEST_DATABASE_URL", "postgresql+psycopg2://eventhub:eventhub_pw@localhost:5432/eventhub_test")
os.environ.setdefault("JWT_SECRET", "test-only-secret-not-used-anywhere-else-0123456789")
os.environ["EXPIRY_SWEEP_SECONDS"] = "1"
os.environ["REQUIRE_EVENT_APPROVAL"] = "true"
os.environ["HOLD_SECONDS"] = "300"

assert os.environ["DATABASE_URL"].rsplit("/", 1)[-1].endswith("_test"), \
    "Refusing to run: the test database name must end with '_test' (it gets wiped)."
