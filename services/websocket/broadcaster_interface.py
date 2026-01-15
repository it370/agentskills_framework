"""
Broadcaster interface for real-time message broadcasting.

This module defines the abstract interface for broadcasters that can send
log and admin events to clients. Implementations include Pusher, Ably, and Socket.IO.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from enum import Enum


class BroadcasterType(Enum):
    """Supported broadcaster types."""
    PUSHER = "pusher"
    ABLY = "ably"
    SOCKETIO = "socketio"


class BroadcasterStatus(Enum):
    """Broadcaster operational status."""
    ACTIVE = "active"           # Working normally
    LIMIT_REACHED = "limit_reached"  # Rate limit or quota reached
    ERROR = "error"             # Experiencing errors
    DISABLED = "disabled"       # Manually disabled


class Broadcaster(ABC):
    """
    Abstract base class for real-time message broadcasters.
    
    All broadcaster implementations must support:
    - Broadcasting logs to 'logs' channel
    - Broadcasting admin events to 'admin' channel
    - Status reporting (active, limited, errored)
    - Graceful degradation when limits are reached
    """
    
    def __init__(self, name: str):
        self.name = name
        self.status = BroadcasterStatus.ACTIVE
        self._error_count = 0
        self._message_count = 0
    
    @abstractmethod
    async def broadcast_log(self, log_data: Dict[str, Any]) -> bool:
        """
        Broadcast a log message to subscribers.
        
        Args:
            log_data: Dict with keys: text, thread_id, level, timestamp
            
        Returns:
            bool: True if successful, False if failed or disabled
        """
        pass
    
    @abstractmethod
    async def broadcast_admin_event(self, payload: Dict[str, Any]) -> bool:
        """
        Broadcast an admin event to subscribers.
        
        Args:
            payload: Event payload (run updates, checkpoint notifications, etc.)
            
        Returns:
            bool: True if successful, False if failed or disabled
        """
        pass
    
    @abstractmethod
    def is_available(self) -> bool:
        """
        Check if broadcaster is available and not rate-limited.
        
        Returns:
            bool: True if can broadcast, False if disabled/limited
        """
        pass
    
    @abstractmethod
    def get_status(self) -> Dict[str, Any]:
        """
        Get current broadcaster status and statistics.
        
        Returns:
            Dict with status, message_count, error_count, etc.
        """
        pass
    
    def _increment_message_count(self):
        """Increment message counter."""
        self._message_count += 1
    
    def _increment_error_count(self):
        """Increment error counter."""
        self._error_count += 1
    
    def _mark_limit_reached(self):
        """Mark broadcaster as rate-limited."""
        self.status = BroadcasterStatus.LIMIT_REACHED
        print(f"[{self.name.upper()}] Rate limit reached, broadcaster disabled for this session")
    
    def _mark_error(self):
        """Mark broadcaster as errored."""
        self.status = BroadcasterStatus.ERROR
        print(f"[{self.name.upper()}] Broadcaster marked as errored")


class NullBroadcaster(Broadcaster):
    """
    Null broadcaster that does nothing (fallback when no broadcaster is available).
    """
    
    def __init__(self):
        super().__init__("null")
        self.status = BroadcasterStatus.DISABLED
    
    async def broadcast_log(self, log_data: Dict[str, Any]) -> bool:
        return False
    
    async def broadcast_admin_event(self, payload: Dict[str, Any]) -> bool:
        return False
    
    def is_available(self) -> bool:
        return False
    
    def get_status(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "status": "disabled",
            "message": "No broadcaster configured"
        }
