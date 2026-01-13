"""
HTTP-based broadcaster for sending events to Socket.IO server.

This module is used by the REST API server to send log and admin events
to the Socket.IO server via HTTP endpoints.
"""

import os
import httpx
from typing import Dict, Any, Optional


# Socket.IO server configuration
SOCKETIO_BASE = f"http://{os.getenv('SOCKETIO_HOST', 'localhost')}:{os.getenv('SOCKETIO_PORT', '7000')}"


async def broadcast_log(log_data: Dict[str, Any]):
    """
    Send a log message to the Socket.IO server via HTTP.
    
    Args:
        log_data: Dict with keys: text, thread_id, level, timestamp
    """
    try:
        async with httpx.AsyncClient(timeout=2.0) as client:
            await client.post(
                f"{SOCKETIO_BASE}/internal/broadcast/log",
                json=log_data
            )
    except Exception as e:
        # Fail silently - don't break workflow execution if Socket.IO is down
        print(f"[HTTP_BROADCASTER] Failed to broadcast log: {e}")


async def broadcast_admin_event(payload: Dict[str, Any]):
    """
    Send an admin event to the Socket.IO server via HTTP.
    
    Args:
        payload: Event payload (run updates, checkpoint notifications, etc.)
    """
    try:
        async with httpx.AsyncClient(timeout=2.0) as client:
            await client.post(
                f"{SOCKETIO_BASE}/internal/broadcast/admin",
                json=payload
            )
    except Exception as e:
        # Fail silently - don't break workflow execution if Socket.IO is down
        print(f"[HTTP_BROADCASTER] Failed to broadcast admin event: {e}")
