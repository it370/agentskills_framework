import os
import sys
import asyncio
import logging
import signal
from pathlib import Path

from env_loader import load_env_once


# Suppress Windows ProactorEventLoop connection reset errors
if sys.platform == 'win32':
    # Suppress "An existing connection was forcibly closed" errors on Windows
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    
    # Filter out noisy connection errors in asyncio
    class SuppressConnectionErrors(logging.Filter):
        def filter(self, record):
            # Suppress ConnectionResetError from ProactorBasePipeTransport
            if "ProactorBasePipeTransport" in record.getMessage():
                return False
            if "WinError 10054" in record.getMessage():
                return False
            return True
    
    logging.getLogger("asyncio").addFilter(SuppressConnectionErrors())


def run():
    """
    Entrypoint to launch REST API server with real-time broadcasting.

    Environment variables:
    - REST_API_HOST: bind address for REST API (default "0.0.0.0")
    - REST_API_PORT: bind port for REST API (default 8000)
    - RELOAD: enable auto-reload (set to "true" to enable; default off)
    - DEFAULT_USER_ID: default user for credential access (default "system")
    - SSL_KEYFILE: path to SSL key file (optional, enables HTTPS)
    - SSL_CERTFILE: path to SSL certificate file (optional, enables HTTPS)
    
    Real-time Broadcasting (Pusher):
    - PUSHER_APP_ID: Pusher application ID
    - PUSHER_KEY: Pusher application key
    - PUSHER_SECRET: Pusher application secret
    - PUSHER_CLUSTER: Pusher cluster (default: ap2)
    """
    
    load_env_once(Path(__file__).resolve().parent)  # Load .env with proper path resolution
    
    # Initialize global auth context for credential access
    try:
        from services.credentials import AuthContext
        auth = AuthContext.initialize_from_env()
        print(f"[AUTH] Initialized global auth context for user: {auth.get_current_user().user_id}")
    except Exception as e:
        print(f"[AUTH] Warning: Could not initialize auth context: {e}")
        print("[AUTH] Credential-based skills may not work without user_context in inputs")
    
    # Configure real-time broadcast integration (Pusher/Ably)
    try:
        from services.websocket import broadcast_log, broadcast_admin_event, get_broadcaster_status
        import log_stream
        import admin_events
        
        log_stream.set_socketio_broadcast(broadcast_log)
        admin_events.set_socketio_broadcast(broadcast_admin_event)
        
        # Show broadcaster status
        status = get_broadcaster_status()
        primary = status.get('primary_broadcaster', 'none')
        available = status.get('primary_available', False)
        broadcast_display = f"{primary.capitalize()} ({'✓' if available else '✗'})"
        
        print(f"[MAIN] Real-time broadcast configured: {primary} ({'available' if available else 'unavailable'})")
        
        if not available:
            print("[MAIN] Warning: Primary broadcaster not available - check configuration")
            broadcaster_type = os.getenv("BROADCASTER_TYPE", "pusher").lower()
            if broadcaster_type == "appsync":
                print("[MAIN] Required env vars: APPSYNC_API_URL, APPSYNC_REGION")
            else:
                print("[MAIN] Required env vars: PUSHER_APP_ID, PUSHER_KEY, PUSHER_SECRET, PUSHER_CLUSTER")
    except Exception as e:
        print(f"[MAIN] Warning: Could not configure broadcast integration: {e}")
        broadcast_display = "Not configured"
    
    # Recover buffered checkpoints from Redis (if any)
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
    
    rest_host = os.getenv("REST_API_HOST", "0.0.0.0")
    rest_port = int(os.getenv("REST_API_PORT", "8000"))
    reload = os.getenv("RELOAD", "false").lower() == "true"
    
    # SSL configuration
    ssl_keyfile = os.getenv("SSL_KEYFILE")
    ssl_certfile = os.getenv("SSL_CERTFILE")
    use_ssl = bool(ssl_keyfile and ssl_certfile)
    protocol = "https" if use_ssl else "http"
    
    print(f"""
╔══════════════════════════════════════════════════════════════╗
║           AgentSkills Framework - Starting Services         ║
╠══════════════════════════════════════════════════════════════╣
║  REST API Server:    {protocol}://{rest_host}:{rest_port:<35}║
║  Real-time Broadcast: {broadcast_display:<44}║
║  SSL/TLS:            {'Enabled' if use_ssl else 'Disabled':<45}║
╚══════════════════════════════════════════════════════════════╝
""")
    
    # Start REST API server
    print("[MAIN] Starting REST API server...")
    try:
        import uvicorn
        uvicorn_config = {
            "app": "api:api",
            "host": rest_host,
            "port": rest_port,
            "reload": reload,
            "timeout_graceful_shutdown": 2,  # Shorter timeout for graceful shutdown
        }
        if use_ssl:
            uvicorn_config["ssl_keyfile"] = ssl_keyfile
            uvicorn_config["ssl_certfile"] = ssl_certfile
        
        uvicorn.run(**uvicorn_config)
    except KeyboardInterrupt:
        print("\n[MAIN] Shutdown signal received")
    except Exception as e:
        print(f"[MAIN] Error: {e}")
    finally:
        try:
            from services.connection_pool import close_pools
            close_pools()
        except Exception as e:
            print(f"[MAIN] Warning: Failed to close connection pools: {e}")
        print("[MAIN] Shutdown complete")


if __name__ == "__main__":
    run()
