import asyncio
import json
from typing import Set, Optional
from contextvars import ContextVar
from datetime import datetime

try:
    from starlette.websockets import WebSocket
except Exception:  # pragma: no cover - typing fallback
    WebSocket = None  # type: ignore

_subscribers: Set["WebSocket"] = set()
_lock = asyncio.Lock()

# SSE clients (queues for Server-Sent Events)
sse_clients = []

# Context variable to store current thread_id for log correlation
_current_thread_id: ContextVar[Optional[str]] = ContextVar("thread_id", default=None)

# Database connection pool (sync pool, accessed via thread)
_db_pool = None


def set_db_pool(pool):
    """Set the database connection pool for log persistence."""
    global _db_pool
    _db_pool = pool


def set_log_context(thread_id: Optional[str]):
    """Set the thread_id context for subsequent log calls."""
    _current_thread_id.set(thread_id)


def get_log_context() -> Optional[str]:
    """Get the current thread_id context."""
    return _current_thread_id.get()


def _persist_log_sync(message: str, thread_id: Optional[str], level: str = "INFO"):
    """Persist log to database (sync version for thread execution)."""
    if not _db_pool:
        return  # No database pool configured
    
    try:
        conn = _db_pool.getconn()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO thread_logs (thread_id, message, level, created_at)
                    VALUES (%s, %s, %s, %s)
                    """,
                    (thread_id, message, level, datetime.utcnow())
                )
            conn.commit()
        finally:
            _db_pool.putconn(conn)
    except Exception as e:
        # Don't let DB errors stop log broadcasting
        print(f"[LOG_PERSIST] Failed to persist log: {e}")


async def _persist_log(message: str, thread_id: Optional[str], level: str = "INFO"):
    """Persist log to database (async wrapper)."""
    await asyncio.to_thread(_persist_log_sync, message, thread_id, level)


async def publish_log(message: str, thread_id: Optional[str] = None, level: str = "INFO"):
    """Broadcast a log line to all connected websocket subscribers and persist to DB.
    
    Args:
        message: The log message text
        thread_id: Optional thread_id. If not provided, uses context variable.
        level: Log level (INFO, WARN, ERROR, DEBUG)
    """
    print(message)
    
    # Use provided thread_id or fall back to context
    tid = thread_id or _current_thread_id.get()
    
    # Persist to database asynchronously (in thread to avoid blocking)
    if _db_pool:
        asyncio.create_task(_persist_log(message, tid, level))
    
    # Send structured JSON message to WebSocket subscribers
    log_data = {
        "text": message,
        "thread_id": tid,
        "level": level,
        "timestamp": None  # Will be set on client side
    }
    log_json = json.dumps(log_data)
    
    # Send to WebSocket clients
    async with _lock:
        dead = []
        for ws in list(_subscribers):
            try:
                await ws.send_text(log_json)
            except Exception:
                dead.append(ws)
        for ws in dead:
            _subscribers.discard(ws)
    
    # Send to SSE clients (non-blocking)
    for client_queue in list(sse_clients):
        try:
            client_queue.put_nowait(log_data)
        except asyncio.QueueFull:
            # Client queue is full, skip this message
            pass
        except Exception:
            # Client may have disconnected
            if client_queue in sse_clients:
                sse_clients.remove(client_queue)


def emit_log(message: str, thread_id: Optional[str] = None, level: str = "INFO"):
    """Fire-and-forget publish from sync contexts.
    
    Args:
        message: The log message text
        thread_id: Optional thread_id. If not provided, uses context variable.
        level: Log level (INFO, WARN, ERROR, DEBUG)
    """
    print(message)
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(publish_log(message, thread_id, level))
    except RuntimeError:
        # No running loop (e.g., import time); fallback is console only.
        pass


async def register(ws: "WebSocket"):
    async with _lock:
        _subscribers.add(ws)


async def unregister(ws: "WebSocket"):
    async with _lock:
        _subscribers.discard(ws)


def _get_thread_logs_sync(thread_id: str, limit: int = 1000):
    """Retrieve historical logs for a specific thread (sync version)."""
    if not _db_pool:
        return []
    
    try:
        conn = _db_pool.getconn()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, thread_id, message, created_at, level
                    FROM thread_logs
                    WHERE thread_id = %s
                    ORDER BY created_at ASC, id ASC
                    LIMIT %s
                    """,
                    (thread_id, limit)
                )
                rows = cur.fetchall()
                return [
                    {
                        "id": row[0],
                        "thread_id": row[1],
                        "message": row[2],
                        "created_at": row[3].isoformat() if row[3] else None,
                        "level": row[4]
                    }
                    for row in rows
                ]
        finally:
            _db_pool.putconn(conn)
    except Exception as e:
        print(f"[LOG_RETRIEVE] Failed to retrieve logs: {e}")
        return []


async def get_thread_logs(thread_id: str, limit: int = 1000):
    """Retrieve historical logs for a specific thread.
    
    Args:
        thread_id: The thread ID to filter logs
        limit: Maximum number of logs to retrieve (default 1000)
        
    Returns:
        List of log dictionaries with keys: id, thread_id, message, created_at, level
    """
    return await asyncio.to_thread(_get_thread_logs_sync, thread_id, limit)



