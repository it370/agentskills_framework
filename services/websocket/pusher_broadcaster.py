"""
Pusher broadcaster implementation.

Sends real-time messages via Pusher Channels with rate limit detection.
"""

import os
import asyncio
from typing import Dict, Any, Optional
from .broadcaster_interface import Broadcaster, BroadcasterStatus

# Import Pusher SDK (will be installed)
try:
    import pusher
    PUSHER_AVAILABLE = True
except ImportError:
    PUSHER_AVAILABLE = False
    print("[PUSHER] pusher library not installed. Run: pip install pusher")


class PusherBroadcaster(Broadcaster):
    """
    Pusher Channels broadcaster implementation.
    
    Features:
    - Automatic rate limit detection (402 Payment Required response)
    - Graceful degradation when limits reached
    - Connection pooling via Pusher SDK
    - Error tracking and reporting
    """
    
    def __init__(
        self,
        app_id: Optional[str] = None,
        key: Optional[str] = None,
        secret: Optional[str] = None,
        cluster: Optional[str] = None,
        use_tls: bool = True
    ):
        super().__init__("pusher")
        
        if not PUSHER_AVAILABLE:
            self.status = BroadcasterStatus.ERROR
            self._client = None
            print("[PUSHER] Cannot initialize: pusher library not available")
            return
        
        # Get config from env or parameters
        self.app_id = app_id or os.getenv("PUSHER_APP_ID")
        self.key = key or os.getenv("PUSHER_KEY")
        self.secret = secret or os.getenv("PUSHER_SECRET")
        self.cluster = cluster or os.getenv("PUSHER_CLUSTER", "ap2")
        self.use_tls = use_tls
        
        # Validate configuration
        if not all([self.app_id, self.key, self.secret]):
            self.status = BroadcasterStatus.ERROR
            self._client = None
            print("[PUSHER] Missing configuration: PUSHER_APP_ID, PUSHER_KEY, or PUSHER_SECRET")
            return
        
        # Initialize Pusher client
        try:
            self._client = pusher.Pusher(
                app_id=self.app_id,
                key=self.key,
                secret=self.secret,
                cluster=self.cluster,
                ssl=self.use_tls
            )
            print(f"[PUSHER] Initialized successfully (cluster: {self.cluster})")
        except Exception as e:
            self.status = BroadcasterStatus.ERROR
            self._client = None
            print(f"[PUSHER] Failed to initialize: {e}")
    
    async def broadcast_log(self, log_data: Dict[str, Any]) -> bool:
        """
        Broadcast log to 'logs' channel.
        
        Args:
            log_data: Dict with keys: text, thread_id, level, timestamp
            
        Returns:
            bool: True if successful, False otherwise
        """
        if not self.is_available():
            return False
        
        try:
            # Pusher trigger is synchronous, run in thread pool
            await asyncio.to_thread(
                self._client.trigger,
                'logs',      # channel
                'log',       # event
                log_data     # data
            )
            self._increment_message_count()
            return True
            
        except Exception as e:
            return self._handle_error(e, "log broadcast")
    
    async def broadcast_admin_event(self, payload: Dict[str, Any]) -> bool:
        """
        Broadcast admin event to 'admin' channel.
        
        Args:
            payload: Event payload
            
        Returns:
            bool: True if successful, False otherwise
        """
        if not self.is_available():
            return False
        
        try:
            # Wrap payload in same format as Socket.IO
            event_data = {
                'type': 'run_event',
                'data': payload
            }
            
            # Pusher trigger is synchronous, run in thread pool
            await asyncio.to_thread(
                self._client.trigger,
                'admin',        # channel
                'admin_event',  # event
                event_data      # data
            )
            self._increment_message_count()
            return True
            
        except Exception as e:
            return self._handle_error(e, "admin event broadcast")
    
    def _handle_error(self, error: Exception, context: str) -> bool:
        """
        Handle broadcast errors with rate limit detection.
        
        Args:
            error: Exception that occurred
            context: Description of what was being done
            
        Returns:
            bool: Always False (broadcast failed)
        """
        error_str = str(error)
        
        # Check for rate limit (HTTP 402 Payment Required)
        if "402" in error_str or "payment required" in error_str.lower():
            self._mark_limit_reached()
            print(f"[PUSHER] Rate limit detected during {context}: {error}")
            print("[PUSHER] Broadcaster disabled for this session. Restart server to re-enable.")
            return False
        
        # Check for other quota/limit errors
        if any(keyword in error_str.lower() for keyword in ["quota", "limit", "exceeded"]):
            self._mark_limit_reached()
            print(f"[PUSHER] Quota/limit error during {context}: {error}")
            print("[PUSHER] Broadcaster disabled for this session. Restart server to re-enable.")
            return False
        
        # Regular error
        self._increment_error_count()
        print(f"[PUSHER] Error during {context}: {error}")
        
        # If too many errors, mark as errored
        if self._error_count >= 10:
            self._mark_error()
            print(f"[PUSHER] Too many errors ({self._error_count}), broadcaster disabled")
        
        return False
    
    def is_available(self) -> bool:
        """
        Check if Pusher broadcaster is available.
        
        Returns:
            bool: True if can broadcast, False if disabled/limited/errored
        """
        return (
            self._client is not None and
            self.status == BroadcasterStatus.ACTIVE
        )
    
    def get_status(self) -> Dict[str, Any]:
        """
        Get current Pusher broadcaster status.
        
        Returns:
            Dict with status information
        """
        return {
            "name": self.name,
            "type": "pusher",
            "status": self.status.value,
            "available": self.is_available(),
            "cluster": self.cluster,
            "use_tls": self.use_tls,
            "message_count": self._message_count,
            "error_count": self._error_count,
            "configured": self._client is not None
        }


def create_pusher_broadcaster() -> PusherBroadcaster:
    """
    Factory function to create Pusher broadcaster from environment variables.
    
    Environment variables:
        PUSHER_APP_ID: Pusher application ID
        PUSHER_KEY: Pusher application key
        PUSHER_SECRET: Pusher application secret
        PUSHER_CLUSTER: Pusher cluster (default: ap2 for Asia Pacific)
    
    Returns:
        PusherBroadcaster instance
    """
    return PusherBroadcaster()
