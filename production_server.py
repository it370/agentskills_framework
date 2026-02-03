"""
Production server for Windows using Hypercorn ASGI server
Hypercorn is a pure-Python production ASGI server that works on Windows
"""
import os
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from env_loader import load_env_once

def run_production():
    """Start production server with Hypercorn"""
    
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
        # Use ASCII-safe characters for Windows
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
    workers = int(os.getenv("HYPERCORN_WORKERS", "4"))
    
    # SSL configuration
    ssl_keyfile = os.getenv("SSL_KEYFILE")
    ssl_certfile = os.getenv("SSL_CERTFILE")
    use_ssl = bool(ssl_keyfile and ssl_certfile)
    protocol = "https" if use_ssl else "http"
    
    print("=" * 66)
    print("  AgentSkills Framework - Production Mode")
    print("=" * 66)
    print(f"  Server:             Hypercorn ASGI Server")
    print(f"  Bind Address:       {protocol}://{host}:{port}")
    print(f"  Workers:            {workers}")
    print(f"  Real-time Broadcast: {broadcast_display}")
    print(f"  SSL/TLS:            {'Enabled' if use_ssl else 'Disabled'}")
    print("=" * 66)
    print()
    
    print("[MAIN] Starting production server with Hypercorn...")
    
    # Build hypercorn command
    bind = f"{host}:{port}"
    cmd_args = [
        "hypercorn",
        "api:api",
        "--bind", bind,
        "--workers", str(workers),
        "--access-logfile", "-",  # stdout
        "--error-logfile", "-",   # stderr
    ]
    
    if use_ssl:
        cmd_args.extend([
            "--certfile", ssl_certfile,
            "--keyfile", ssl_keyfile
        ])
    
    # Run hypercorn
    import subprocess
    try:
        subprocess.run(cmd_args)
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
