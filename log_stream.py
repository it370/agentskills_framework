"""
Log streaming module.

Logs are broadcast in real-time via SSE (Server-Sent Events) and persisted to
the database via an end-of-run flush from Redis (or directly if Redis is
unavailable). No per-line DB writes.
"""
import asyncio
from typing import Optional
from contextvars import ContextVar
from datetime import datetime

# Context variable to store current thread_id for log correlation
_current_thread_id: ContextVar[Optional[str]] = ContextVar("thread_id", default=None)


def set_db_pool(pool):
    """Deprecated shim kept for backwards compatibility."""
    print("[LOG_STREAM] WARNING: set_db_pool() is deprecated and has no effect.")


def set_log_context(thread_id: Optional[str], broadcast: bool = True):
    """Set the thread_id context for subsequent log calls.

    The ``broadcast`` parameter is accepted for backwards compatibility but
    ignored – all logs are always forwarded over SSE.
    """
    _current_thread_id.set(thread_id)


def get_log_context() -> Optional[str]:
    """Return the current thread_id context."""
    return _current_thread_id.get()


async def publish_log(message: str, thread_id: Optional[str] = None, level: str = "INFO"):
    """Broadcast a log line over SSE (Redis-backed) and print to stdout.

    DB persistence happens at end-of-run via flush, not per line.
    """
    print(message)

    tid = thread_id or _current_thread_id.get()

    log_data = {
        "text": message,
        "thread_id": tid,
        "level": level,
        "timestamp": datetime.utcnow().isoformat(),
    }

    try:
        from services.websocket.sse_broadcast import broadcast_log_sse
        await broadcast_log_sse(log_data)
    except Exception as e:
        print(f"[LOG_STREAM] SSE broadcast error: {e}")


def emit_log(message: str, thread_id: Optional[str] = None, level: str = "INFO"):
    """Fire-and-forget publish from sync contexts."""
    print(message)
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(publish_log(message, thread_id, level))
    except RuntimeError:
        pass


def _get_thread_logs_sync(thread_id: str, limit: int = 1000):
    """Retrieve historical logs for a thread (sync, uses connection pool)."""
    try:
        from services.connection_pool import get_postgres_pool
        pool = get_postgres_pool()
    except (RuntimeError, ImportError):
        return []

    try:
        conn = pool.getconn()
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
                    (thread_id, limit),
                )
                rows = cur.fetchall()
                return [
                    {
                        "id": row[0],
                        "thread_id": row[1],
                        "message": row[2],
                        "created_at": row[3].isoformat() if row[3] else None,
                        "level": row[4],
                    }
                    for row in rows
                ]
        finally:
            pool.putconn(conn)
    except Exception as e:
        print(f"[LOG_RETRIEVE] Failed to retrieve logs: {e}")
        return []


async def get_thread_logs(thread_id: str, limit: int = 1000):
    """Retrieve historical logs for a thread (async)."""
    return await asyncio.to_thread(_get_thread_logs_sync, thread_id, limit)
