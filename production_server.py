"""
Production server for Windows using Uvicorn ASGI server
Optimized for production with proper event loop and connection handling
"""
import os
import sys
import asyncio
import logging
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from env_loader import load_env_once

# Suppress Windows ProactorEventLoop connection reset errors
if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    
    class SuppressConnectionErrors(logging.Filter):
        def filter(self, record):
            if "ProactorBasePipeTransport" in record.getMessage():
                return False
            if "WinError 10054" in record.getMessage():
                return False
            return True
    
    logging.getLogger("asyncio").addFilter(SuppressConnectionErrors())

def run_production():
    """Start production server with Uvicorn (optimized for production)"""
    
    # Load environment
    load_env_once(Path(__file__).resolve().parent)
    
    # Initialize auth context
    try:
        from services.credentials import AuthContext
        auth = AuthContext.initialize_from_env()
        print(f"[AUTH] Initialized global auth context for user: {auth.get_current_user().user_id}")
    except Exception as e:
        print(f"[AUTH] Warning: Could not initialize auth context: {e}")
    
    # Configure broadcast integration
    try:
        from services.websocket import broadcast_log, broadcast_admin_event, get_broadcaster_status
        import log_stream
        import admin_events
        
        log_stream.set_socketio_broadcast(broadcast_log)
        admin_events.set_socketio_broadcast(broadcast_admin_event)
        
        status = get_broadcaster_status()
        primary = status.get('primary_broadcaster', 'none')
        available = status.get('primary_available', False)
        broadcast_display = f"{primary.capitalize()} ({'OK' if available else 'FAIL'})"
        
        print(f"[MAIN] Real-time broadcast configured: {primary} ({'available' if available else 'unavailable'})")
    except Exception as e:
        print(f"[MAIN] Warning: Could not configure broadcast integration: {e}")
        broadcast_display = "Not configured"
    
    # Recover buffered checkpoints
    try:
        import asyncio
        from services.checkpoint_buffer import recover_buffered_checkpoints
        from engine import _get_env_value
        
        db_uri = _get_env_value("DATABASE_URL", "")
        if db_uri:
            print("[MAIN] Checking for buffered checkpoints to recover...")
            asyncio.run(recover_buffered_checkpoints(db_uri))
    except Exception as e:
        print(f"[MAIN] Warning: Could not recover buffered checkpoints: {e}")
    
    # Configuration
    host = os.getenv("REST_API_HOST", "0.0.0.0")
    port = int(os.getenv("REST_API_PORT", "8000"))
    
    # SSL configuration
    ssl_keyfile = os.getenv("SSL_KEYFILE")
    ssl_certfile = os.getenv("SSL_CERTFILE")
    use_ssl = bool(ssl_keyfile and ssl_certfile)
    protocol = "https" if use_ssl else "http"
    
    print("=" * 66)
    print("  AgentSkills Framework - Production Mode")
    print("=" * 66)
    print(f"  Server:             Uvicorn ASGI Server (Production)")
    print(f"  Bind Address:       {protocol}://{host}:{port}")
    print(f"  Workers:            1 (async, optimized for Windows)")
    print(f"  Real-time Broadcast: {broadcast_display}")
    print(f"  SSL/TLS:            {'Enabled' if use_ssl else 'Disabled'}")
    print("=" * 66)
    print()
    
    print("[MAIN] Starting production server with Uvicorn...")
    
    # Run Uvicorn with production settings
    try:
        import uvicorn
        uvicorn_config = {
            "app": "api:api",
            "host": host,
            "port": port,
            "reload": False,  # Production: no auto-reload
            "log_level": "info",
            "access_log": True,
            "timeout_graceful_shutdown": 5,
            "limit_concurrency": 1000,  # Production: handle more concurrent connections
            "limit_max_requests": None,  # No request limit
            "timeout_keep_alive": 5,
        }
        
        if use_ssl:
            uvicorn_config["ssl_keyfile"] = ssl_keyfile
            uvicorn_config["ssl_certfile"] = ssl_certfile
        
        uvicorn.run(**uvicorn_config)
    except KeyboardInterrupt:
        print("\n[MAIN] Shutdown signal received")
    except Exception as e:
        print(f"[MAIN] Error: {e}")
        raise
    finally:
        try:
            from services.connection_pool import close_pools
            close_pools()
        except Exception as e:
            print(f"[MAIN] Warning: Failed to close connection pools: {e}")
        print("[MAIN] Shutdown complete")


if __name__ == "__main__":
    run_production()
