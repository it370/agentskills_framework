"""
WebSocket/Real-time broadcasting service module.

This module provides real-time communication for:
- Log streaming (real-time logs from workflow execution)
- Admin events (workflow status updates, checkpoint notifications)

Supports multiple broadcaster backends:
- Pusher (primary, cloud-hosted)
- Ably (future fallback)
- Socket.IO (legacy, self-hosted)
"""

from .broadcaster_manager import (
    BroadcasterManager,
    get_broadcaster_manager,
    initialize_broadcaster_manager,
)
from .broadcaster_interface import (
    Broadcaster,
    BroadcasterType,
    BroadcasterStatus,
)

# Initialize the broadcaster manager
_manager = None


def get_manager() -> BroadcasterManager:
    """Get the global broadcaster manager."""
    global _manager
    if _manager is None:
        _manager = initialize_broadcaster_manager()
    return _manager


async def broadcast_log(log_data: dict) -> bool:
    """
    Broadcast a log message to all subscribers.
    
    Args:
        log_data: Dict with keys: text, thread_id, level, timestamp
        
    Returns:
        bool: True if successful
    """
    manager = get_manager()
    return await manager.broadcast_log(log_data)


async def broadcast_admin_event(payload: dict) -> bool:
    """
    Broadcast an admin event to all subscribers.
    
    Args:
        payload: Event payload
        
    Returns:
        bool: True if successful
    """
    manager = get_manager()
    return await manager.broadcast_admin_event(payload)


def get_broadcaster_status() -> dict:
    """
    Get status of all broadcasters.
    
    Returns:
        Dict with broadcaster statuses
    """
    manager = get_manager()
    return manager.get_status()


__all__ = [
    'broadcast_log',
    'broadcast_admin_event',
    'get_broadcaster_status',
    'BroadcasterManager',
    'get_broadcaster_manager',
    'initialize_broadcaster_manager',
    'Broadcaster',
    'BroadcasterType',
    'BroadcasterStatus',
]
