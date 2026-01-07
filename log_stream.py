import asyncio
from typing import Set

try:
    from starlette.websockets import WebSocket
except Exception:  # pragma: no cover - typing fallback
    WebSocket = None  # type: ignore

_subscribers: Set["WebSocket"] = set()
_lock = asyncio.Lock()


async def publish_log(message: str):
    """Broadcast a log line to all connected websocket subscribers."""
    print(message)
    async with _lock:
        dead = []
        for ws in list(_subscribers):
            try:
                await ws.send_text(message)
            except Exception:
                dead.append(ws)
        for ws in dead:
            _subscribers.discard(ws)


def emit_log(message: str):
    """Fire-and-forget publish from sync contexts."""
    print(message)
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(publish_log(message))
    except RuntimeError:
        # No running loop (e.g., import time); fallback is console only.
        pass


async def register(ws: "WebSocket"):
    async with _lock:
        _subscribers.add(ws)


async def unregister(ws: "WebSocket"):
    async with _lock:
        _subscribers.discard(ws)

