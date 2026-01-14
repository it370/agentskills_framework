import os
import subprocess
import sys
import asyncio
import logging
import signal
from pathlib import Path

from dotenv import load_dotenv


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


# Global reference to subprocess for signal handlers
socketio_process = None


def shutdown_handler(signum, frame):
    """Handle shutdown signals (Ctrl+C, SIGTERM)"""
    global socketio_process
    print("\n[MAIN] Shutdown signal received, cleaning up...")
    
    # Kill Socket.IO server immediately
    if socketio_process and socketio_process.poll() is None:
        print("[MAIN] Terminating Socket.IO server...")
        socketio_process.terminate()
        try:
            socketio_process.wait(timeout=2)
            print("[MAIN] Socket.IO server stopped")
        except subprocess.TimeoutExpired:
            print("[MAIN] Force killing Socket.IO server...")
            socketio_process.kill()
            socketio_process.wait()
    
    print("[MAIN] Shutdown complete")
    sys.exit(0)


def run():
    """
    Entrypoint to launch both REST API and Socket.IO servers.

    Environment variables:
    - REST_API_HOST: bind address for REST API (default "0.0.0.0")
    - REST_API_PORT: bind port for REST API (default 8000)
    - SOCKETIO_HOST: bind address for Socket.IO (default "0.0.0.0")
    - SOCKETIO_PORT: bind port for Socket.IO (default 7000)
    - RELOAD: enable auto-reload (set to "true" to enable; default off)
    - DEFAULT_USER_ID: default user for credential access (default "system")
    - SSL_KEYFILE: path to SSL key file (optional, enables HTTPS)
    - SSL_CERTFILE: path to SSL certificate file (optional, enables HTTPS)
    """
    global socketio_process
    
    load_dotenv()  # pick up .env before reading config
    
    # Register signal handlers for clean shutdown
    signal.signal(signal.SIGINT, shutdown_handler)
    signal.signal(signal.SIGTERM, shutdown_handler)
    
    # Initialize global auth context for credential access
    try:
        from services.credentials import AuthContext
        auth = AuthContext.initialize_from_env()
        print(f"[AUTH] Initialized global auth context for user: {auth.get_current_user().user_id}")
    except Exception as e:
        print(f"[AUTH] Warning: Could not initialize auth context: {e}")
        print("[AUTH] Credential-based skills may not work without user_context in inputs")
    
    # Configure Socket.IO broadcast integration via HTTP
    try:
        from services.websocket.http_broadcaster import broadcast_log, broadcast_admin_event
        import log_stream
        import admin_events
        
        log_stream.set_socketio_broadcast(broadcast_log)
        admin_events.set_socketio_broadcast(broadcast_admin_event)
        print("[MAIN] Socket.IO HTTP broadcast integration configured")
    except Exception as e:
        print(f"[MAIN] Warning: Could not configure Socket.IO integration: {e}")
    
    rest_host = os.getenv("REST_API_HOST", "0.0.0.0")
    rest_port = int(os.getenv("REST_API_PORT", "8000"))
    socketio_host = os.getenv("SOCKETIO_HOST", "0.0.0.0")
    socketio_port = int(os.getenv("SOCKETIO_PORT", "7000"))
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
║  Socket.IO Server:   {protocol}://{socketio_host}:{socketio_port:<35}║
║  SSL/TLS:            {'Enabled' if use_ssl else 'Disabled':<45}║
╚══════════════════════════════════════════════════════════════╝
""")
    
    # Get the project root
    project_root = Path(__file__).resolve().parent
    
    # Build Socket.IO server command
    socketio_cmd = [
        sys.executable, "-m", "uvicorn", "socketio_server:socket_app",
        "--host", socketio_host, "--port", str(socketio_port)
    ]
    if use_ssl:
        socketio_cmd.extend(["--ssl-keyfile", ssl_keyfile, "--ssl-certfile", ssl_certfile])
    
    # Start Socket.IO server in background
    print("[MAIN] Starting Socket.IO server...")
    socketio_process = subprocess.Popen(
        socketio_cmd,
        cwd=str(project_root),
        env=os.environ.copy(),
        # Redirect output to suppress noise during shutdown
        stdout=subprocess.PIPE if not reload else None,
        stderr=subprocess.PIPE if not reload else None
    )
    
    # Start REST API server (foreground)
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
        # Signal handler will take care of cleanup
        pass
    except Exception as e:
        print(f"[MAIN] Error: {e}")
    finally:
        # Cleanup Socket.IO server (in case signal handler didn't run)
        if socketio_process and socketio_process.poll() is None:
            print("[MAIN] Stopping Socket.IO server...")
            socketio_process.terminate()
            try:
                socketio_process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                socketio_process.kill()
                socketio_process.wait()
            print("[MAIN] Shutdown complete")


if __name__ == "__main__":
    run()
