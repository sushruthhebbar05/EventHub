
import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text

from app.config import settings
from app.database import engine
from app.routes import admin, auth, bookings, events, holds, organiser, payments, tickets, users, venues
from app.services.seat_service import sweep_expired_holds
from app.utils.errors import AppError
from app.websocket.manager import manager
from app.websocket.routes import router as ws_router

log = logging.getLogger("eventhub")
STATIC_DIR = Path(__file__).resolve().parent / "static"


async def hold_expiry_loop() -> None:
    """Background task: every few seconds, release holds that ran out and tell connected browsers."""
    while True:
        try:
            changes = await run_in_threadpool(sweep_expired_holds)
            for event_id, seat_status in changes.items():
                await manager.broadcast(event_id, {
                    "type": "seat_update", "event_id": event_id,
                    "seats": [{"seat_id": s, "status": st} for s, st in seat_status.items()]})
        except asyncio.CancelledError:
            raise
        except Exception:
            log.exception("hold expiry sweep failed")
        await asyncio.sleep(settings.expiry_sweep_seconds)


@asynccontextmanager
async def lifespan(app: FastAPI):
    manager.loop = asyncio.get_running_loop()
    task = asyncio.create_task(hold_expiry_loop())
    yield
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass


tags_metadata = [
    {"name": "Authentication", "description": "Register, log in, current user."},
    {"name": "Users", "description": "Your own profile."},
    {"name": "Events", "description": "Browse, search and manage events."},
    {"name": "Venues", "description": "Venues where events take place."},
    {"name": "Seats", "description": "Live seat map of an event."},
    {"name": "Holds", "description": "Temporary 5-minute seat holds (concurrency-safe)."},
    {"name": "Bookings", "description": "Checkout, booking history, cancellation (idempotent)."},
    {"name": "Payments", "description": "Mock payment gateway (idempotent)."},
    {"name": "Tickets", "description": "QR e-tickets, downloads and entry check-in."},
    {"name": "Organiser Dashboard", "description": "Sales and availability for your own events."},
    {"name": "Admin", "description": "User management, event approval, platform statistics."},
]

app = FastAPI(title="EventHub API", version="1.0.0", lifespan=lifespan, openapi_tags=tags_metadata,
              description="Event discovery & real-time ticket booking. Real-time seat updates: `ws://localhost:8000/ws/events/{event_id}`.")

app.add_middleware(CORSMiddleware, allow_origins=[o.strip() for o in settings.cors_origins.split(",")],
                   allow_credentials=True, allow_methods=["*"], allow_headers=["*"])


@app.exception_handler(AppError)
async def app_error_handler(_: Request, exc: AppError):
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.message, **exc.extra},
                        headers={"WWW-Authenticate": "Bearer"} if exc.status_code == 401 else None)


@app.exception_handler(RequestValidationError)
async def validation_handler(_: Request, exc: RequestValidationError):
    errors = exc.errors()
    first = errors[0] if errors else {}
    field = ".".join(str(p) for p in first.get("loc", []) if p not in ("body", "query", "header", "path"))
    message = f"{field}: {first.get('msg', 'Invalid input')}" if field else first.get("msg", "Invalid input")
    return JSONResponse(status_code=422, content={"detail": message.replace("Value error, ", ""),
                                                  "errors": [{"field": ".".join(str(p) for p in e["loc"]), "message": e["msg"]} for e in errors]})


for r in (auth.router, users.router, events.router, venues.router, holds.router, bookings.router,
          payments.router, tickets.router, organiser.router, admin.router):
    app.include_router(r)
app.include_router(ws_router)
STATIC_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/api/health", tags=["Health"])
def health():
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
    return {"status": "ok"}
