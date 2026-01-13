import asyncio
from typing import Optional
from contextvars import ContextVar
from datetime import datetime

# External Socket.IO server integration
_external_socketio_broadcast = None  # Will be set to services.websocket.broadcast_log

# Context variable to store current thread_id for log correlation
_current_thread_id: ContextVar[Optional[str]] = ContextVar("thread_id", default=None)

# Database connection pool (sync pool, accessed via thread)
_db_pool = None


def set_db_pool(pool):
    """Set the database connection pool for log persistence."""
    global _db_pool
    _db_pool = pool


def set_socketio_broadcast(broadcast_func):
    """
    Set Socket.IO broadcast function.
    
    This allows log_stream to send logs to the Socket.IO server
    running on port 7000.
    
    Args:
        broadcast_func: Async function that takes a dict and broadcasts it
    """
    global _external_socketio_broadcast
    _external_socketio_broadcast = broadcast_func
    print("[LOG_STREAM] Socket.IO broadcast configured")


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
    """Broadcast a log line to Socket.IO subscribers and persist to DB.
    
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
    
    # Send structured message to Socket.IO server
    log_data = {
        "text": message,
        "thread_id": tid,
        "level": level,
        "timestamp": datetime.utcnow().isoformat()
    }
    
    # Broadcast to Socket.IO server (if configured)
    if _external_socketio_broadcast:
        try:
            await _external_socketio_broadcast(log_data)
        except Exception as e:
            print(f"[LOG_STREAM] Error broadcasting to Socket.IO: {e}")


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
