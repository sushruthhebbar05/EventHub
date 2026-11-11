"""Keeps track of which browsers are watching which event and pushes seat updates to them.

Route handlers are plain (sync) functions that run in a thread pool, so `notify()` is thread-safe:
it schedules the async broadcast on the main event loop.
"""
import asyncio
import logging
from collections import defaultdict

from fastapi import WebSocket

log = logging.getLogger("eventhub.ws")


class ConnectionManager:
    def __init__(self) -> None:
        self.rooms: dict[int, set[WebSocket]] = defaultdict(set)
        self.loop: asyncio.AbstractEventLoop | None = None

    async def connect(self, event_id: int, ws: WebSocket) -> None:
        await ws.accept()
        self.rooms[event_id].add(ws)

    def disconnect(self, event_id: int, ws: WebSocket) -> None:
        self.rooms[event_id].discard(ws)
        if not self.rooms[event_id]:
            self.rooms.pop(event_id, None)

    async def broadcast(self, event_id: int, message: dict) -> None:
        for ws in list(self.rooms.get(event_id, ())):
            try:
                await ws.send_json(message)
            except Exception:  # a dead/closed socket must never break the others
                self.disconnect(event_id, ws)

    def notify(self, event_id: int, seat_ids: list[int], status_by_seat: dict[int, str]) -> None:
        """Tell everyone viewing `event_id` that these seats changed. Safe to call from any thread."""
        if not seat_ids or self.loop is None or not self.loop.is_running():
            return
        message = {
            "type": "seat_update",
            "event_id": event_id,
            "seats": [{"seat_id": sid, "status": status_by_seat[sid]} for sid in seat_ids],
        }
        asyncio.run_coroutine_threadsafe(self.broadcast(event_id, message), self.loop)


manager = ConnectionManager()
