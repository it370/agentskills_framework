"""
Admin events broadcasting via SSE.
"""
from typing import Dict, Any


def set_socketio_broadcast(broadcast_func):
    """Deprecated shim kept for backwards compatibility."""
    print("[ADMIN_EVENTS] WARNING: set_socketio_broadcast() is deprecated and has no effect.")


async def broadcast_run_event(payload: Dict[str, Any]):
    """Broadcast a run event to all SSE admin subscribers."""
    try:
        from services.websocket.sse_broadcast import broadcast_admin_sse
        await broadcast_admin_sse(payload)
    except Exception as e:
        print(f"[ADMIN_EVENTS] SSE broadcast error: {e}")
