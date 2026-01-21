"""
AWS AppSync Event API broadcaster implementation.

Publishes messages via WebSocket with message batching for performance.
"""

import os
import asyncio
import json
import base64
import uuid
from urllib.parse import urlparse
from typing import Dict, Any, Optional, List
from .broadcaster_interface import Broadcaster, BroadcasterStatus

# Import websockets for WebSocket publishing
try:
    import websockets
    from websockets.exceptions import ConnectionClosed
    WEBSOCKETS_AVAILABLE = True
except ImportError:
    WEBSOCKETS_AVAILABLE = False
    print("[APPSYNC] websockets library not installed. Run: pip install websockets")


class AppSyncBroadcaster(Broadcaster):
    """
    AWS AppSync Event API broadcaster using WebSocket publishing with batching.
    
    Features:
    - WebSocket publishing for low-latency events
    - 200ms message batching for high-frequency logs
    - Automatic flush on shutdown
    """
    
    def __init__(
        self,
        api_url: Optional[str] = None,
        api_id: Optional[str] = None,
        api_key: Optional[str] = None,
        region: Optional[str] = None,
        namespace: Optional[str] = None,
        batch_interval: float = 0.2  # 200ms batching
    ):
        super().__init__("appsync")
        
        if not WEBSOCKETS_AVAILABLE:
            self.status = BroadcasterStatus.ERROR
            self._ws = None
            print("[APPSYNC] Cannot initialize: websockets library not available")
            return
        
        # Get config from env or parameters
        self.api_url = api_url or os.getenv("APPSYNC_API_URL")
        self.api_id = api_id or os.getenv("APPSYNC_API_ID")
        self.api_key = api_key or os.getenv("APPSYNC_API_KEY")
        self.region = region or os.getenv("APPSYNC_REGION", "us-east-1")
        self.namespace = namespace or os.getenv("APPSYNC_NAMESPACE", "default")
        self.batch_interval = batch_interval
        
        # Validate configuration
        if not self.api_url:
            self.status = BroadcasterStatus.ERROR
            self._ws = None
            print("[APPSYNC] Missing configuration: APPSYNC_API_URL is required")
            return
        
        if not self.api_key:
            self.status = BroadcasterStatus.ERROR
            self._ws = None
            print("[APPSYNC] Missing configuration: APPSYNC_API_KEY is required")
            return
        
        # Message batching
        self._message_batches: Dict[str, List[Dict[str, Any]]] = {}  # channel -> [messages]
        self._batch_lock = asyncio.Lock()
        self._flush_task: Optional[asyncio.Task] = None
        self._running = False
        
        # WebSocket connection state
        try:
            self._ws: Optional[websockets.WebSocketClientProtocol] = None
            self._ws_lock = asyncio.Lock()
            self._ws_reader_task: Optional[asyncio.Task] = None

            # Parse API URL
            api_url_for_parse = self.api_url if "://" in self.api_url else f"https://{self.api_url}"
            parsed = urlparse(api_url_for_parse)
            raw_host = parsed.netloc
            if not raw_host:
                raise ValueError("Invalid APPSYNC_API_URL (missing host)")
            if "/event" not in parsed.path:
                print("[APPSYNC] Warning: APPSYNC_API_URL should end with /event")

            # Determine HTTP host (for auth) and realtime host (for WS)
            if "appsync-realtime-api." in raw_host:
                self.http_host = raw_host.replace("appsync-realtime-api.", "appsync-api.")
                self.realtime_host = raw_host
            elif "appsync-api." in raw_host:
                self.http_host = raw_host
                self.realtime_host = raw_host.replace("appsync-api.", "appsync-realtime-api.")
            else:
                # Custom domain or other host: use same host for both
                self.http_host = raw_host
                self.realtime_host = raw_host

            # Normalize realtime path
            ws_path = parsed.path
            if ws_path.endswith("/event/realtime"):
                pass
            elif ws_path.endswith("/event") or ws_path.endswith("/event/"):
                ws_path = "/event/realtime"
            else:
                ws_path = "/event/realtime"

            self.ws_url = f"wss://{self.realtime_host}{ws_path}"

            print(f"[APPSYNC] Initialized successfully")
            print(f"[APPSYNC]   Region: {self.region}")
            print(f"[APPSYNC]   API ID: {self.api_id}")
            print(f"[APPSYNC]   Namespace: {self.namespace}")
            print(f"[APPSYNC]   Batch interval: {self.batch_interval * 1000}ms")
            print(f"[APPSYNC]   WebSocket endpoint: {self.ws_url}")
            
            # Start background flush task (lazily on first use)
            self._running = True
            self._flush_task = None  # Will be created on first broadcast
            
        except Exception as e:
            self.status = BroadcasterStatus.ERROR
            self._ws = None
            print(f"[APPSYNC] Failed to initialize: {e}")
    
    def _ensure_flush_task(self):
        """Ensure the background flush task is running (lazy initialization)."""
        if self._flush_task is None and self._running:
            try:
                self._flush_task = asyncio.create_task(self._batch_flush_loop())
                print("[APPSYNC] Started background batch flush task")
            except RuntimeError:
                # No event loop yet, will retry on next call
                pass
    async def _batch_flush_loop(self):
        """Background task that flushes batches every 200ms."""
        try:
            while self._running:
                await asyncio.sleep(self.batch_interval)
                await self._flush_batches()
        except asyncio.CancelledError:
            # Flush remaining messages on shutdown
            await self._flush_batches()
            raise
        except Exception as e:
            print(f"[APPSYNC] Error in batch flush loop: {e}")
    
    async def _flush_batches(self):
        """Flush all pending message batches."""
        async with self._batch_lock:
            if not self._message_batches:
                return
            
            # Process each channel's batched messages
            for channel, messages in list(self._message_batches.items()):
                if messages:
                    await self._send_batch(channel, messages)
                    self._message_batches[channel] = []
    
    def _build_auth_subprotocol(self) -> str:
        """Build the AppSync auth subprotocol header (base64url)."""
        auth_header = {
            "host": self.http_host,
            "x-api-key": self.api_key
        }
        header_json = json.dumps(auth_header).encode("utf-8")
        header_b64 = base64.b64encode(header_json).decode("ascii")
        header_b64 = header_b64.replace("+", "-").replace("/", "_").rstrip("=")
        return f"header-{header_b64}"

    async def _connect_ws(self) -> None:
        """Connect to AppSync Event API WebSocket endpoint."""
        auth_protocol = self._build_auth_subprotocol()
        subprotocols = ["aws-appsync-event-ws", auth_protocol]
        self._ws = await websockets.connect(
            self.ws_url,
            subprotocols=subprotocols,
            ping_interval=20,
            ping_timeout=20
        )
        if self._ws_reader_task is None or self._ws_reader_task.done():
            self._ws_reader_task = asyncio.create_task(self._ws_reader_loop())
        print("[APPSYNC] ✅ WebSocket connected")

    async def _ensure_ws_connected(self) -> bool:
        """Ensure the WebSocket connection is open."""
        if self._ws and not getattr(self._ws, "closed", False):
            return True
        async with self._ws_lock:
            if self._ws and not getattr(self._ws, "closed", False):
                return True
            try:
                await self._connect_ws()
                return True
            except Exception as e:
                print(f"[APPSYNC] ❌ WebSocket connect failed: {e}")
                self._increment_error_count()
                return False

    async def _ws_reader_loop(self) -> None:
        """Read messages from AppSync WebSocket (publish ack/errors)."""
        try:
            while self._running and self._ws:
                message = await self._ws.recv()
                self._handle_ws_message(message)
        except ConnectionClosed:
            pass
        except Exception as e:
            print(f"[APPSYNC] WebSocket reader error: {e}")
        finally:
            self._ws = None

    def _handle_ws_message(self, raw_message: str) -> None:
        """Handle WebSocket messages (publish_success / publish_error)."""
        try:
            message = json.loads(raw_message)
        except Exception:
            return

        msg_type = message.get("type")
        if msg_type == "publish_success":
            msg_id = message.get("id")
            print(f"[APPSYNC] ✅ Publish success (id: {msg_id})")
        elif msg_type == "publish_error":
            msg_id = message.get("id")
            error_info = message.get("errors") or message.get("message")
            print(f"[APPSYNC] ❌ Publish error (id: {msg_id}): {error_info}")
            self._increment_error_count()
        elif msg_type == "connection_error":
            print(f"[APPSYNC] ❌ Connection error: {message}")
            self._increment_error_count()

    async def _send_batch(self, channel: str, messages: List[Dict[str, Any]]):
        """Send a batch of messages to a channel via WebSocket."""
        try:
            if not await self._ensure_ws_connected():
                return False

            # Convert messages to AppSync event payloads (max 5 events per publish)
            events = [
                json.dumps({"event": msg["event"], "data": msg["data"]})
                for msg in messages
            ]
            chunks = [events[i:i + 5] for i in range(0, len(events), 5)]

            for chunk in chunks:
                publish_message = {
                    "id": str(uuid.uuid4()),
                    "type": "publish",
                    "channel": channel,
                    "events": chunk,
                    "authorization": {
                        "host": self.http_host,
                        "x-api-key": self.api_key
                    }
                }
                await self._ws.send(json.dumps(publish_message))
                self._message_count += len(chunk)

            if len(messages) > 1:
                print(f"[APPSYNC] ✅ Sent {len(messages)} messages to '{channel}'")
            return True

        except Exception as e:
            print(f"[APPSYNC] ❌ Error sending batch to {channel}: {e}")
            self._increment_error_count()
            return False
    
    async def broadcast_log(self, log_data: Dict[str, Any]) -> bool:
        """
        Broadcast log to 'logs' channel (batched).
        
        Args:
            log_data: Dict with keys: text, thread_id, level, timestamp
            
        Returns:
            bool: True if queued successfully
        """
        if not self.is_available():
            return False
        
        # Ensure flush task is running
        self._ensure_flush_task()
        
        try:
            # Use namespaced channel name
            channel = f"{self.namespace}/logs"
            
            # Add to batch
            async with self._batch_lock:
                if channel not in self._message_batches:
                    self._message_batches[channel] = []
                
                self._message_batches[channel].append({
                    'event': 'log',
                    'data': log_data
                })
            
            return True
            
        except Exception as e:
            return self._handle_error(e, "log broadcast")
    
    async def broadcast_admin_event(self, payload: Dict[str, Any]) -> bool:
        """
        Broadcast admin event to 'admin' channel (batched).
        
        Args:
            payload: Event payload
            
        Returns:
            bool: True if queued successfully
        """
        if not self.is_available():
            return False
        
        # Ensure flush task is running
        self._ensure_flush_task()
        
        try:
            # Wrap payload in same format as Pusher
            event_data = {
                'type': 'run_event',
                'data': payload
            }
            
            # Use namespaced channel name
            channel = f"{self.namespace}/admin"
            
            # Add to batch
            async with self._batch_lock:
                if channel not in self._message_batches:
                    self._message_batches[channel] = []
                
                self._message_batches[channel].append({
                    'event': 'admin_event',
                    'data': event_data
                })
            
            return True
            
        except Exception as e:
            return self._handle_error(e, "admin event broadcast")
    
    def _handle_error(self, error: Exception, context: str) -> bool:
        """
        Handle broadcast errors.
        
        Args:
            error: Exception that occurred
            context: Description of what was being done
            
        Returns:
            bool: Always False (broadcast failed)
        """
        error_str = str(error)
        
        # Check for rate limit/throttling
        if any(keyword in error_str.lower() for keyword in ["throttl", "limit", "quota", "exceeded"]):
            self._mark_limit_reached()
            print(f"[APPSYNC] Rate limit detected during {context}: {error}")
            print("[APPSYNC] Broadcaster disabled for this session. Restart server to re-enable.")
            return False
        
        # Regular error
        self._increment_error_count()
        print(f"[APPSYNC] Error during {context}: {error}")
        
        # If too many errors, mark as errored
        if self._error_count >= 10:
            self._mark_error()
            print(f"[APPSYNC] Too many errors ({self._error_count}), broadcaster disabled")
        
        return False
    
    def is_available(self) -> bool:
        """
        Check if AppSync broadcaster is available.
        
        Returns:
            bool: True if can broadcast, False if disabled/limited/errored
        """
        return self._running and self.status == BroadcasterStatus.ACTIVE
    
    def get_status(self) -> Dict[str, Any]:
        """
        Get current AppSync broadcaster status.
        
        Returns:
            Dict with status information
        """
        total_queued = sum(len(msgs) for msgs in self._message_batches.values())
        
        return {
            "name": self.name,
            "type": "appsync",
            "status": self.status.value,
            "available": self.is_available(),
            "region": self.region,
            "api_id": self.api_id if hasattr(self, 'api_id') else None,
            "namespace": self.namespace if hasattr(self, 'namespace') else None,
            "auth_mode": "API_KEY",
            "message_count": self._message_count,
            "error_count": self._error_count,
            "queued_messages": total_queued,
            "batch_interval_ms": self.batch_interval * 1000,
            "configured": self._running
        }
    
    async def shutdown(self):
        """Gracefully shutdown the broadcaster."""
        print("[APPSYNC] Shutting down...")
        self._running = False
        
        if self._flush_task:
            self._flush_task.cancel()
            try:
                await self._flush_task
            except asyncio.CancelledError:
                pass
        
        # Final flush
        await self._flush_batches()

        # Close WebSocket
        if self._ws:
            await self._ws.close()
            self._ws = None

        if self._ws_reader_task:
            self._ws_reader_task.cancel()
            try:
                await self._ws_reader_task
            except asyncio.CancelledError:
                pass
        
        print("[APPSYNC] Shutdown complete")
    
    async def __aenter__(self):
        """Async context manager entry."""
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit - cleanup."""
        await self.shutdown()


def create_appsync_broadcaster() -> AppSyncBroadcaster:
    """
    Factory function to create AppSync broadcaster from environment variables.
    
    Environment variables:
        APPSYNC_API_URL: AppSync Event API endpoint URL
        APPSYNC_API_ID: AppSync API ID
        APPSYNC_API_KEY: AppSync API key (required)
        APPSYNC_REGION: AWS region (default: us-east-1)
        APPSYNC_NAMESPACE: Channel namespace (default: default)
    
    Returns:
        AppSyncBroadcaster instance
    """
    return AppSyncBroadcaster()
