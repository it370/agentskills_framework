import os
import subprocess
import sys
from pathlib import Path

from dotenv import load_dotenv


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
    """
    load_dotenv()  # pick up .env before reading config
    
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
    
    print(f"""
╔══════════════════════════════════════════════════════════════╗
║           AgentSkills Framework - Starting Services         ║
╠══════════════════════════════════════════════════════════════╣
║  REST API Server:    http://{rest_host}:{rest_port:<35}║
║  Socket.IO Server:   http://{socketio_host}:{socketio_port:<35}║
╚══════════════════════════════════════════════════════════════╝
""")
    
    # Get the project root
    project_root = Path(__file__).resolve().parent
    
    # Start Socket.IO server in background
    print("[MAIN] Starting Socket.IO server...")
    socketio_process = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "socketio_server:socket_app", 
         "--host", socketio_host, "--port", str(socketio_port)],
        cwd=str(project_root),
        env=os.environ.copy()
    )
    
    # Start REST API server (foreground)
    print("[MAIN] Starting REST API server...")
    try:
        import uvicorn
        uvicorn.run("api:api", host=rest_host, port=rest_port, reload=reload)
    except KeyboardInterrupt:
        print("\n[MAIN] Shutting down...")
    finally:
        # Cleanup Socket.IO server
        print("[MAIN] Stopping Socket.IO server...")
        socketio_process.terminate()
        socketio_process.wait(timeout=5)
        print("[MAIN] Shutdown complete")


if __name__ == "__main__":
    run()
