"""
Standalone Socket.IO Server

Real-time communication server using Socket.IO for:
- Log streaming from workflow execution (/logs namespace)
- Admin events (run updates, checkpoint notifications) (/admin namespace)

Runs independently on port 7000 (default) separate from REST API.

Environment Variables:
    SOCKETIO_HOST: Bind address (default: 0.0.0.0)
    SOCKETIO_PORT: Bind port (default: 7000)
    SOCKETIO_CORS_ORIGINS: CORS origins, comma-separated (default: *)
"""

import os
from pathlib import Path

import socketio
import uvicorn
from fastapi import FastAPI

from env_loader import load_env_once
from services.websocket import (
    initialize_socketio,
    register_socketio_handlers,
    initialize_event_listeners,
    shutdown_event_listeners,
    get_connection_stats,
)

# Load environment
load_env_once(Path(__file__).resolve().parent)

# Configuration
SOCKETIO_HOST = os.getenv("SOCKETIO_HOST", "0.0.0.0")
SOCKETIO_PORT = int(os.getenv("SOCKETIO_PORT", "7000"))
CORS_ORIGINS = [
    o.strip() for o in os.getenv("SOCKETIO_CORS_ORIGINS", "*").split(",") if o.strip()
]

# Create Socket.IO server
sio = socketio.AsyncServer(
    async_mode='asgi',
    cors_allowed_origins=CORS_ORIGINS if "*" not in CORS_ORIGINS else "*",
    logger=False,
    engineio_logger=False,
)

# Create FastAPI app
app = FastAPI(
    title="AgentSkills Socket.IO Server",
    description="Real-time communication server for logs and admin events",
    version="1.0.0",
)

# Combine Socket.IO with FastAPI
socket_app = socketio.ASGIApp(sio, app)

# Initialize Socket.IO
initialize_socketio(sio)
register_socketio_handlers(sio)


@app.on_event("startup")
async def startup():
    """Initialize background services on server startup."""
    print(f"[SOCKETIO_SERVER] Starting Socket.IO server on {SOCKETIO_HOST}:{SOCKETIO_PORT}")
    initialize_event_listeners()
    print("[SOCKETIO_SERVER] Startup complete")


@app.on_event("shutdown")
async def shutdown():
    """Cleanup on server shutdown."""
    print("[SOCKETIO_SERVER] Shutting down Socket.IO server...")
    shutdown_event_listeners()
    print("[SOCKETIO_SERVER] Shutdown complete")


@app.get("/")
async def root():
    """Root endpoint with server info."""
    stats = get_connection_stats()
    return {
        "service": "AgentSkills Socket.IO Server",
        "version": "1.0.0",
        "protocol": "Socket.IO",
        "namespaces": {
            "/logs": "Log streaming from workflow execution",
            "/admin": "Admin events and run updates",
        },
        "endpoints": {
            "health": "/health",
            "stats": "/stats",
        },
        "connections": stats,
    }


@app.get("/health")
async def health_check():
    """Health check endpoint for monitoring."""
    stats = get_connection_stats()
    return {
        "status": "healthy",
        "service": "socketio",
        "port": SOCKETIO_PORT,
        "connections": stats,
    }


@app.get("/stats")
async def socketio_stats():
    """Get current Socket.IO connection statistics."""
    stats = get_connection_stats()
    return {
        "status": "success",
        "stats": stats,
    }


@app.post("/internal/broadcast/log")
async def internal_broadcast_log(log_data: dict):
    """
    Internal endpoint for REST API to broadcast logs to Socket.IO clients.
    
    This is called by the REST API server process to send logs to connected clients.
    """
    from services.websocket import broadcast_log as socketio_broadcast_log
    try:
        await socketio_broadcast_log(log_data)
        return {"status": "success"}
    except Exception as e:
        print(f"[SOCKETIO_SERVER] Error broadcasting log: {e}")
        return {"status": "error", "message": str(e)}


@app.post("/internal/broadcast/admin")
async def internal_broadcast_admin(payload: dict):
    """
    Internal endpoint for REST API to broadcast admin events to Socket.IO clients.
    
    This is called by the REST API server process to send admin events to connected clients.
    """
    from services.websocket import broadcast_admin_event as socketio_broadcast_admin
    try:
        await socketio_broadcast_admin(payload)
        return {"status": "success"}
    except Exception as e:
        print(f"[SOCKETIO_SERVER] Error broadcasting admin event: {e}")
        return {"status": "error", "message": str(e)}


def run():
    """
    Run the Socket.IO server.
    
    This is the main entry point when running as a standalone service.
    """
    print(f"""
╔══════════════════════════════════════════════════════════╗
║     AgentSkills Socket.IO Server                        ║
║     Port: {SOCKETIO_PORT:<45} ║
║     Host: {SOCKETIO_HOST:<45} ║
╚══════════════════════════════════════════════════════════╝

Socket.IO Namespaces:
  • {SOCKETIO_HOST}:{SOCKETIO_PORT}/logs  - Log streaming
  • {SOCKETIO_HOST}:{SOCKETIO_PORT}/admin - Admin events

HTTP Endpoints:
  • GET http://{SOCKETIO_HOST}:{SOCKETIO_PORT}/        - Server info
  • GET http://{SOCKETIO_HOST}:{SOCKETIO_PORT}/health  - Health check
  • GET http://{SOCKETIO_HOST}:{SOCKETIO_PORT}/stats   - Connection stats

Press Ctrl+C to stop
""")
    
    uvicorn.run(
        socket_app,
        host=SOCKETIO_HOST,
        port=SOCKETIO_PORT,
        log_level="info",
    )


if __name__ == "__main__":
    run()
