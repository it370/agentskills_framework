import asyncio
import json
from typing import Set, Dict, Any

try:
    from starlette.websockets import WebSocket
except Exception:  # pragma: no cover - typing fallback
    WebSocket = None  # type: ignore

_subscribers: Set["WebSocket"] = set()
_lock = asyncio.Lock()


async def broadcast_run_event(payload: Dict[str, Any]):
    """Broadcast a run event payload to all connected admin websocket clients."""
    message = json.dumps({"type": "run_event", "data": payload})
    async with _lock:
        dead = []
        for ws in list(_subscribers):
            try:
                await ws.send_text(message)
            except Exception:
                dead.append(ws)
        for ws in dead:
            _subscribers.discard(ws)


async def register_admin(ws: "WebSocket"):
    async with _lock:
        _subscribers.add(ws)


async def unregister_admin(ws: "WebSocket"):
    async with _lock:
        _subscribers.discard(ws)

