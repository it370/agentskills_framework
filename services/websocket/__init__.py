"""
Socket.IO service module for real-time communication.

This module provides Socket.IO endpoints for:
- Log streaming (real-time logs from workflow execution) - /logs namespace
- Admin events (workflow status updates, checkpoint notifications) - /admin namespace

The Socket.IO server runs independently on port 7000 (configurable)
separate from the REST API server on port 8000.
"""

from .socketio_events import (
    initialize_socketio,
    broadcast_log,
    broadcast_admin_event,
    initialize_event_listeners,
    shutdown_event_listeners,
    get_connection_stats,
    register_socketio_handlers,
)

__all__ = [
    'initialize_socketio',
    'broadcast_log',
    'broadcast_admin_event',
    'initialize_event_listeners',
    'shutdown_event_listeners',
    'get_connection_stats',
    'register_socketio_handlers',
]
