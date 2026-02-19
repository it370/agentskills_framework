"""
SSE (Server-Sent Events) broadcast for logs and admin events.

When BROADCASTER_TYPE=sse:
- Logs: push to Redis (durability) + push to in-memory subscribers (immediate UX).
  Per-thread subscribers and global subscribers supported.
- Admin: push to in-memory global subscribers only.
- No historical replay from Redis on client connect.
- Flush Redis to DB at end of run and on app restart.
"""

import asyncio
import json
from typing import Dict, Any, Set, Optional

# In-memory: per-thread log subscribers and global log subscribers
_log_subscribers: Dict[str, Set[asyncio.Queue]] = {}  # thread_id -> set of queues
_global_log_subscribers: Set[asyncio.Queue] = set()
_admin_subscribers: Set[asyncio.Queue] = set()
_admin_subscribers_by_thread: Dict[str, Set[asyncio.Queue]] = {}
_QUEUE_MAXSIZE = 1000


def _put_queue(queue: asyncio.Queue, data: dict) -> None:
    try:
        queue.put_nowait(data)
    except asyncio.QueueFull:
        pass


async def broadcast_log_sse(log_data: dict) -> bool:
    """
    Push log to the queue (Redis if available, local in-process buffer otherwise)
    and forward to all in-memory SSE subscribers immediately.

    Durability: logs are batch-flushed to the DB at run end by the queue's
    flush_thread_to_db_sync / flush_all_to_db_sync methods.  The queue itself
    handles the Redis-vs-local decision transparently.
    """
    from . import log_queue as log_queue_module
    thread_id = (log_data or {}).get("thread_id") or ""
    # 1. Queue (Redis or local fallback) — batch-flushed to DB at run end
    queue = log_queue_module.get_log_queue()
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, queue.push, thread_id, log_data)
    # 2. SSE: per-thread subscribers
    for q in _log_subscribers.get(thread_id, set()):
        _put_queue(q, log_data)
    # 3. SSE: global subscribers
    for q in _global_log_subscribers:
        _put_queue(q, log_data)
    return True


async def broadcast_admin_sse(payload: dict) -> bool:
    """Push admin event to admin SSE subscribers (global + per-thread)."""
    thread_id = (payload or {}).get("thread_id")
    event_type = (payload or {}).get("type") or (payload or {}).get("event")
    if thread_id and event_type == "workflow_ui_update":
        try:
            from .admin_event_queue import get_admin_event_queue
            queue = get_admin_event_queue()
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, queue.push, thread_id, payload)
        except Exception as exc:
            print(f"[SSE] Failed to queue workflow_ui_update for persistence: {exc}")
    for q in _admin_subscribers:
        _put_queue(q, payload)
    if thread_id:
        for q in _admin_subscribers_by_thread.get(thread_id, set()):
            _put_queue(q, payload)
    return True


def get_sse_status() -> dict:
    """Status for BROADCASTER_TYPE=sse."""
    per_thread = sum(len(s) for s in _log_subscribers.values())
    admin_thread_scoped = sum(len(s) for s in _admin_subscribers_by_thread.values())
    return {
        "primary_broadcaster": "sse",
        "primary_available": True,
        "total_broadcasters": 1,
        "available_broadcasters": 1,
        "broadcasters": [{
            "name": "sse",
            "type": "sse",
            "status": "active",
            "available": True,
            "log_subscribers_per_thread": per_thread,
            "log_subscribers_global": len(_global_log_subscribers),
            "admin_subscribers": len(_admin_subscribers),
            "admin_subscribers_thread_scoped": admin_thread_scoped,
        }],
    }


async def stream_logs_sse(thread_id: Optional[str]):
    """
    Async generator: stream log events as SSE. If thread_id is None, stream all logs (global).
    No historical replay from Redis.
    """
    q = asyncio.Queue(maxsize=_QUEUE_MAXSIZE)
    try:
        if thread_id:
            _log_subscribers.setdefault(thread_id, set()).add(q)
        else:
            _global_log_subscribers.add(q)
        while True:
            try:
                msg = await asyncio.wait_for(q.get(), timeout=30.0)
                yield f"data: {json.dumps(msg)}\n\n"
            except asyncio.TimeoutError:
                yield ": keepalive\n\n"
    finally:
        if thread_id and thread_id in _log_subscribers:
            _log_subscribers[thread_id].discard(q)
            if not _log_subscribers[thread_id]:
                del _log_subscribers[thread_id]
        _global_log_subscribers.discard(q)


async def stream_admin_sse(thread_id: Optional[str] = None):
    """Async generator: stream admin events as SSE (global or per-thread)."""
    q = asyncio.Queue(maxsize=_QUEUE_MAXSIZE)
    try:
        if thread_id:
            _admin_subscribers_by_thread.setdefault(thread_id, set()).add(q)
        else:
            _admin_subscribers.add(q)
        while True:
            try:
                msg = await asyncio.wait_for(q.get(), timeout=30.0)
                yield f"data: {json.dumps(msg)}\n\n"
            except asyncio.TimeoutError:
                yield ": keepalive\n\n"
    finally:
        if thread_id and thread_id in _admin_subscribers_by_thread:
            _admin_subscribers_by_thread[thread_id].discard(q)
            if not _admin_subscribers_by_thread[thread_id]:
                del _admin_subscribers_by_thread[thread_id]
        _admin_subscribers.discard(q)
