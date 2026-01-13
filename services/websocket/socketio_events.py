"""
Socket.IO event handlers and broadcasting.

Manages real-time communication using Socket.IO for:
- Log streaming from workflow execution
- Admin events (run updates, checkpoint notifications)
"""

import asyncio
import threading
from typing import Dict, Any, Optional
from pathlib import Path


# Socket.IO server instance (set during initialization)
sio = None

# Pub/Sub listener state
_pubsub_client = None
_listener_thread = None
_listener_stop_flag = threading.Event()


def initialize_socketio(socketio_server):
    """
    Initialize the Socket.IO server instance.
    
    Args:
        socketio_server: AsyncServer instance from python-socketio
    """
    global sio
    sio = socketio_server
    print("[SOCKETIO] Server instance initialized")


async def broadcast_log(log_data: Dict[str, Any]):
    """
    Broadcast a log message to all connected log subscribers.
    
    Args:
        log_data: Dict with keys: text, thread_id, level, timestamp
    """
    if not sio:
        return
    
    try:
        await sio.emit('log', log_data, namespace='/logs')
    except Exception as e:
        print(f"[SOCKETIO] Error broadcasting log: {e}")


async def broadcast_admin_event(payload: Dict[str, Any]):
    """
    Broadcast an admin event to all admin subscribers.
    
    Args:
        payload: Event payload (run updates, checkpoint notifications, etc.)
    """
    if not sio:
        return
    
    try:
        await sio.emit('admin_event', {
            'type': 'run_event',
            'data': payload
        }, namespace='/admin')
    except Exception as e:
        print(f"[SOCKETIO] Error broadcasting admin event: {e}")


def _pubsub_event_listener():
    """
    Listen for pub/sub events and forward to Socket.IO clients.
    Runs in a background thread.
    """
    global _pubsub_client
    
    try:
        from services.pubsub import create_pubsub_client
        from env_loader import load_env_once
        
        # Load environment
        load_env_once(Path(__file__).resolve().parents[2])
        
        # Create pub/sub client
        _pubsub_client = create_pubsub_client()
        
        print(f"[SOCKETIO] Starting pub/sub event listener")
        
        # Callback for incoming messages
        def on_message(payload: Dict[str, Any]):
            # Forward to async broadcast from thread
            try:
                loop = asyncio.new_event_loop()
                loop.run_until_complete(broadcast_admin_event(payload))
                loop.close()
            except Exception as e:
                print(f"[SOCKETIO] Error forwarding pub/sub message: {e}")
        
        # Listen (blocking call)
        _pubsub_client.listen('run_events', on_message, _listener_stop_flag)
        
    except Exception as exc:
        print(f"[SOCKETIO] Pub/sub event listener error: {exc}")
    finally:
        if _pubsub_client:
            _pubsub_client.close()


def initialize_event_listeners():
    """
    Initialize background event listeners (pub/sub).
    Call this on server startup.
    """
    global _listener_thread
    
    if _listener_thread and _listener_thread.is_alive():
        print("[SOCKETIO] Event listeners already running")
        return
    
    _listener_stop_flag.clear()
    _listener_thread = threading.Thread(
        target=_pubsub_event_listener,
        daemon=True,
        name="socketio-pubsub-listener"
    )
    _listener_thread.start()
    print("[SOCKETIO] Event listeners initialized")


def shutdown_event_listeners():
    """
    Shutdown background event listeners.
    Call this on server shutdown.
    """
    global _listener_thread, _pubsub_client
    
    print("[SOCKETIO] Shutting down event listeners...")
    
    # Signal the thread to stop
    _listener_stop_flag.set()
    
    # Close the client to interrupt blocking operations
    if _pubsub_client:
        try:
            _pubsub_client.close()
        except Exception as e:
            print(f"[SOCKETIO] Error closing pubsub client: {e}")
    
    # Wait briefly for thread to finish
    if _listener_thread and _listener_thread.is_alive():
        _listener_thread.join(timeout=0.5)
        if _listener_thread.is_alive():
            print("[SOCKETIO] Listener thread still running (will be terminated by daemon flag)")
    
    print("[SOCKETIO] Event listeners shutdown complete")


# Connection tracking for stats
_connections = {
    'logs': 0,
    'admin': 0,
}


def get_connection_stats() -> Dict[str, Any]:
    """Get current connection statistics."""
    return {
        "log_connections": _connections['logs'],
        "admin_connections": _connections['admin'],
        "total_connections": _connections['logs'] + _connections['admin'],
    }


def _increment_connections(namespace: str):
    """Increment connection count for namespace."""
    key = namespace.strip('/') if namespace else 'default'
    _connections[key] = _connections.get(key, 0) + 1


def _decrement_connections(namespace: str):
    """Decrement connection count for namespace."""
    key = namespace.strip('/') if namespace else 'default'
    _connections[key] = max(0, _connections.get(key, 0) - 1)


# Socket.IO event handlers

def register_socketio_handlers(socketio_server):
    """
    Register Socket.IO event handlers.
    
    Args:
        socketio_server: AsyncServer instance
    """
    
    @socketio_server.event(namespace='/logs')
    async def connect(sid, environ):
        """Handle client connection to logs namespace."""
        _increment_connections('logs')
        print(f"[SOCKETIO] Log client connected: {sid} (total: {_connections['logs']})")
    
    @socketio_server.event(namespace='/logs')
    async def disconnect(sid):
        """Handle client disconnection from logs namespace."""
        _decrement_connections('logs')
        print(f"[SOCKETIO] Log client disconnected: {sid} (total: {_connections['logs']})")
    
    @socketio_server.event(namespace='/admin')
    async def connect(sid, environ):
        """Handle client connection to admin namespace."""
        _increment_connections('admin')
        print(f"[SOCKETIO] Admin client connected: {sid} (total: {_connections['admin']})")
    
    @socketio_server.event(namespace='/admin')
    async def disconnect(sid):
        """Handle client disconnection from admin namespace."""
        _decrement_connections('admin')
        print(f"[SOCKETIO] Admin client disconnected: {sid} (total: {_connections['admin']})")
    
    print("[SOCKETIO] Event handlers registered")
