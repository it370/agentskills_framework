from typing import Dict, Any

# External Socket.IO server integration
_external_socketio_broadcast = None  # Will be set to services.websocket.broadcast_admin_event


def set_socketio_broadcast(broadcast_func):
    """
    Set Socket.IO broadcast function.
    
    This allows admin_events to send events to the Socket.IO server
    running on port 7000.
    
    Args:
        broadcast_func: Async function that takes a dict and broadcasts it
    """
    global _external_socketio_broadcast
    _external_socketio_broadcast = broadcast_func
    print("[ADMIN_EVENTS] Socket.IO broadcast configured")


async def broadcast_run_event(payload: Dict[str, Any]):
    """Broadcast a run event payload to Socket.IO admin subscribers."""
    
    # Broadcast to Socket.IO server (if configured)
    if _external_socketio_broadcast:
        try:
            await _external_socketio_broadcast(payload)
        except Exception as e:
            print(f"[ADMIN_EVENTS] Error broadcasting to Socket.IO: {e}")
