"""
Broadcaster manager with fallback support.

Manages multiple broadcasters with automatic fallback when primary fails or reaches limits.
"""

from typing import Dict, Any, List, Optional
from .broadcaster_interface import Broadcaster, BroadcasterStatus, NullBroadcaster


class BroadcasterManager:
    """
    Manages multiple broadcasters with fallback support.
    
    Features:
    - Primary broadcaster with automatic fallback
    - Broadcasts to all available broadcasters simultaneously (future: optional)
    - Status reporting across all broadcasters
    - Graceful degradation when broadcasters fail
    
    Usage:
        manager = BroadcasterManager()
        manager.add_broadcaster(pusher_broadcaster, primary=True)
        manager.add_broadcaster(ably_broadcaster, primary=False)  # Fallback
        
        await manager.broadcast_log(log_data)  # Uses primary, falls back if needed
    """
    
    def __init__(self):
        self._broadcasters: List[Broadcaster] = []
        self._primary: Optional[Broadcaster] = None
        self._broadcast_to_all = False  # Future: enable multi-broadcast
    
    def add_broadcaster(self, broadcaster: Broadcaster, primary: bool = False):
        """
        Add a broadcaster to the manager.
        
        Args:
            broadcaster: Broadcaster instance
            primary: If True, this becomes the primary broadcaster
        """
        if broadcaster not in self._broadcasters:
            self._broadcasters.append(broadcaster)
            print(f"[BROADCASTER_MANAGER] Added broadcaster: {broadcaster.name}")
        
        if primary:
            self._primary = broadcaster
            print(f"[BROADCASTER_MANAGER] Set primary broadcaster: {broadcaster.name}")
    
    def set_broadcast_to_all(self, enabled: bool):
        """
        Enable/disable broadcasting to all available broadcasters.
        
        Args:
            enabled: If True, broadcasts to all available broadcasters
        """
        self._broadcast_to_all = enabled
        print(f"[BROADCASTER_MANAGER] Broadcast to all: {enabled}")
    
    async def broadcast_log(self, log_data: Dict[str, Any]) -> bool:
        """
        Broadcast log using available broadcaster(s).
        
        Strategy:
        - If broadcast_to_all is enabled: Send to all available broadcasters
        - Otherwise: Try primary, then fallback to next available if primary fails
        
        Args:
            log_data: Log data to broadcast
            
        Returns:
            bool: True if at least one broadcaster succeeded
        """
        if self._broadcast_to_all:
            return await self._broadcast_to_all_available(log_data, 'log')
        else:
            return await self._broadcast_with_fallback(log_data, 'log')
    
    async def broadcast_admin_event(self, payload: Dict[str, Any]) -> bool:
        """
        Broadcast admin event using available broadcaster(s).
        
        Strategy:
        - If broadcast_to_all is enabled: Send to all available broadcasters
        - Otherwise: Try primary, then fallback to next available if primary fails
        
        Args:
            payload: Event payload to broadcast
            
        Returns:
            bool: True if at least one broadcaster succeeded
        """
        if self._broadcast_to_all:
            return await self._broadcast_to_all_available(payload, 'admin')
        else:
            return await self._broadcast_with_fallback(payload, 'admin')
    
    async def _broadcast_with_fallback(
        self,
        data: Dict[str, Any],
        message_type: str
    ) -> bool:
        """
        Broadcast using primary broadcaster with fallback.
        
        Args:
            data: Data to broadcast
            message_type: 'log' or 'admin'
            
        Returns:
            bool: True if any broadcaster succeeded
        """
        # Try primary first
        if self._primary and self._primary.is_available():
            success = await self._broadcast_single(self._primary, data, message_type)
            if success:
                return True
        
        # Primary failed or unavailable, try fallbacks
        for broadcaster in self._broadcasters:
            if broadcaster == self._primary:
                continue  # Already tried
            
            if broadcaster.is_available():
                success = await self._broadcast_single(broadcaster, data, message_type)
                if success:
                    print(f"[BROADCASTER_MANAGER] Fallback to {broadcaster.name} succeeded")
                    return True
        
        # All broadcasters failed
        return False
    
    async def _broadcast_to_all_available(
        self,
        data: Dict[str, Any],
        message_type: str
    ) -> bool:
        """
        Broadcast to all available broadcasters simultaneously.
        
        Args:
            data: Data to broadcast
            message_type: 'log' or 'admin'
            
        Returns:
            bool: True if at least one broadcaster succeeded
        """
        import asyncio
        
        tasks = []
        for broadcaster in self._broadcasters:
            if broadcaster.is_available():
                task = self._broadcast_single(broadcaster, data, message_type)
                tasks.append(task)
        
        if not tasks:
            return False
        
        # Wait for all broadcasts to complete
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Return True if at least one succeeded
        return any(result is True for result in results)
    
    async def _broadcast_single(
        self,
        broadcaster: Broadcaster,
        data: Dict[str, Any],
        message_type: str
    ) -> bool:
        """
        Broadcast to a single broadcaster.
        
        Args:
            broadcaster: Broadcaster to use
            data: Data to broadcast
            message_type: 'log' or 'admin'
            
        Returns:
            bool: True if successful
        """
        try:
            if message_type == 'log':
                return await broadcaster.broadcast_log(data)
            elif message_type == 'admin':
                return await broadcaster.broadcast_admin_event(data)
            else:
                print(f"[BROADCASTER_MANAGER] Unknown message type: {message_type}")
                return False
        except Exception as e:
            print(f"[BROADCASTER_MANAGER] Error broadcasting to {broadcaster.name}: {e}")
            return False
    
    def get_status(self) -> Dict[str, Any]:
        """
        Get status of all broadcasters.
        
        Returns:
            Dict with overall status and individual broadcaster statuses
        """
        broadcaster_statuses = [b.get_status() for b in self._broadcasters]
        
        available_count = sum(1 for b in self._broadcasters if b.is_available())
        
        primary_name = self._primary.name if self._primary else "none"
        primary_available = self._primary.is_available() if self._primary else False
        
        return {
            "primary_broadcaster": primary_name,
            "primary_available": primary_available,
            "total_broadcasters": len(self._broadcasters),
            "available_broadcasters": available_count,
            "broadcast_to_all": self._broadcast_to_all,
            "broadcasters": broadcaster_statuses
        }


# Global broadcaster manager instance
_manager: Optional[BroadcasterManager] = None


def get_broadcaster_manager() -> BroadcasterManager:
    """
    Get the global broadcaster manager instance.
    
    Returns:
        BroadcasterManager singleton
    """
    global _manager
    if _manager is None:
        _manager = BroadcasterManager()
    return _manager


def initialize_broadcaster_manager() -> BroadcasterManager:
    """
    Initialize the broadcaster manager with default configuration.
    
    This creates a manager with Pusher as primary and prepares for future Ably fallback.
    
    Returns:
        Configured BroadcasterManager
    """
    from .pusher_broadcaster import create_pusher_broadcaster
    
    manager = get_broadcaster_manager()
    
    # Add Pusher as primary
    pusher = create_pusher_broadcaster()
    manager.add_broadcaster(pusher, primary=True)
    
    # Future: Add Ably as fallback
    # ably = create_ably_broadcaster()
    # manager.add_broadcaster(ably, primary=False)
    
    print("[BROADCASTER_MANAGER] Initialized with Pusher as primary")
    
    return manager
