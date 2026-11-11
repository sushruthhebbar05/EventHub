from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.websocket.manager import manager

router = APIRouter()


@router.websocket("/ws/events/{event_id}")
async def event_seats_socket(websocket: WebSocket, event_id: int):
    """Browsers viewing an event's seat map connect here and receive `seat_update` messages.

    The socket is read-only for seat data (all changes go through the REST API so they are
    authenticated and transactional). The client may send "ping" to keep the connection alive.
    """
    await manager.connect(event_id, websocket)
    try:
        await websocket.send_json({"type": "connected", "event_id": event_id})
        while True:
            text = await websocket.receive_text()
            if text == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        pass
    except Exception:
        pass
    finally:
        manager.disconnect(event_id, websocket)
