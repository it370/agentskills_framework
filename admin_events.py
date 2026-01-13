import asyncio
import json
from typing import Set, Dict, Any

try:
    from starlette.websockets import WebSocket
except Exception:  # pragma: no cover - typing fallback
    WebSocket = None  # type: ignore

_subscribers: Set["WebSocket"] = set()
_lock = asyncio.Lock()

# SSE clients (queues for Server-Sent Events)
sse_clients = []


async def broadcast_run_event(payload: Dict[str, Any]):
    """Broadcast a run event payload to all connected admin websocket clients."""
    message_data = {"type": "run_event", "data": payload}
    message = json.dumps(message_data)
    
    # Send to WebSocket clients
    async with _lock:
        dead = []
        for ws in list(_subscribers):
            try:
                await ws.send_text(message)
            except Exception:
                dead.append(ws)
        for ws in dead:
            _subscribers.discard(ws)
    
    # Send to SSE clients (non-blocking)
    for client_queue in list(sse_clients):
        try:
            client_queue.put_nowait(message_data)
        except asyncio.QueueFull:
            # Client queue is full, skip this message
            pass
        except Exception:
            # Client may have disconnected
            if client_queue in sse_clients:
                sse_clients.remove(client_queue)


async def register_admin(ws: "WebSocket"):
    async with _lock:
        _subscribers.add(ws)


async def unregister_admin(ws: "WebSocket"):
    async with _lock:
        _subscribers.discard(ws)

