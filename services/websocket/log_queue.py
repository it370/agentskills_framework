"""
Log queue for SSE-path durability.

Primary backend: Redis (logs:queue:{thread_id}).
Fallback when Redis is unavailable: in-process dict keyed by thread_id.

In both cases logs accumulate in the queue and are flushed to the DB in a
single batch INSERT at run end (completed / error / cancelled / paused) and on
app restart — never one INSERT per log line.
"""

import os
import json
import asyncio
import threading
from typing import Dict, Any, List, Optional
from datetime import datetime

try:
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False

LOG_QUEUE_KEY_PREFIX = "logs:queue:"


def _redis_params_from_env() -> Dict[str, Any]:
    """Build Redis connection params from environment variables."""
    host = os.getenv("REDIS_HOST", "localhost")
    try:
        port = int(os.getenv("REDIS_PORT", "6379"))
    except (ValueError, TypeError):
        port = 6379
    redis_db_str = os.getenv("REDIS_DB", "0")
    try:
        db = int(redis_db_str)
        use_db_param = True
    except (ValueError, TypeError):
        db = 0
        use_db_param = False
    password = os.getenv("REDIS_PASSWORD", None) or None
    params = {
        "host": host,
        "port": port,
        "password": password,
        "decode_responses": True,
        "socket_connect_timeout": 5,
        "socket_timeout": 5,
    }
    if use_db_param:
        params["db"] = db
    return params


def _insert_logs_batch(conn, logs_by_thread: Dict[str, List[Dict[str, Any]]]) -> int:
    """INSERT a batch of logs into thread_logs. Returns total rows inserted."""
    total = 0
    with conn.cursor() as cur:
        for thread_id, entries in logs_by_thread.items():
            for entry in entries:
                msg = entry.get("text") or ""
                level = entry.get("level") or "INFO"
                ts = entry.get("timestamp")
                if isinstance(ts, str):
                    try:
                        created = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                    except Exception:
                        created = datetime.utcnow()
                else:
                    created = datetime.utcnow()
                cur.execute(
                    """
                    INSERT INTO thread_logs (thread_id, message, level, created_at)
                    VALUES (%s, %s, %s, %s)
                    """,
                    (thread_id, msg, level, created),
                )
                total += 1
    conn.commit()
    return total


class RedisLogQueue:
    """
    Fan-in log queue with automatic local fallback.

    When Redis is reachable logs go into Redis lists (one per thread).
    When Redis is unavailable logs accumulate in an in-process dict instead —
    still batched, still flushed as a single INSERT at run end.

    All public methods are thread-safe.
    """

    def __init__(self):
        self._client: Optional["redis.Redis"] = None
        self._available: Optional[bool] = None  # None = not yet probed

        # Local fallback buffer: thread_id -> list of log dicts
        self._local: Dict[str, List[Dict[str, Any]]] = {}
        self._local_lock = threading.Lock()

    # ------------------------------------------------------------------
    # Redis plumbing
    # ------------------------------------------------------------------

    def _key(self, thread_id: str) -> str:
        return f"{LOG_QUEUE_KEY_PREFIX}{thread_id}"

    def _get_client(self) -> Optional["redis.Redis"]:
        if not REDIS_AVAILABLE:
            return None
        if self._available is False:
            return None
        if self._client is not None:
            return self._client
        try:
            self._client = redis.Redis(**_redis_params_from_env())
            self._client.ping()
            self._available = True
            print("[LOG_QUEUE] Connected to Redis for log fan-in")
            return self._client
        except Exception as e:
            print(f"[LOG_QUEUE] Redis unavailable – using local in-process buffer: {e}")
            self._available = False
            self._client = None
            return None

    def is_available(self) -> bool:
        """True when the Redis backend is reachable."""
        return self._get_client() is not None

    # ------------------------------------------------------------------
    # Push (write path)
    # ------------------------------------------------------------------

    def push(self, thread_id: str, log_data: Dict[str, Any]) -> bool:
        """
        Append one log entry to the queue (Redis or local fallback).
        Always returns True so callers don't need to handle failure.
        """
        client = self._get_client()
        if client is not None:
            try:
                client.rpush(self._key(thread_id), json.dumps(log_data))
                return True
            except Exception as e:
                print(f"[LOG_QUEUE] Redis push failed, falling back to local buffer: {e}")
                self._available = False
                self._client = None
                # Fall through to local buffer below

        # Local in-process fallback
        with self._local_lock:
            self._local.setdefault(thread_id, []).append(log_data)
        return True

    # ------------------------------------------------------------------
    # Drain helpers (read + clear)
    # ------------------------------------------------------------------

    def _drain_redis_thread(self, thread_id: str) -> List[Dict[str, Any]]:
        client = self._get_client()
        if client is None:
            return []
        try:
            key = self._key(thread_id)
            raw = client.lrange(key, 0, -1)
            if raw:
                client.delete(key)
            return [json.loads(s) for s in raw if s]
        except Exception as e:
            print(f"[LOG_QUEUE] Redis drain_thread failed: {e}")
            return []

    def _drain_local_thread(self, thread_id: str) -> List[Dict[str, Any]]:
        with self._local_lock:
            return self._local.pop(thread_id, [])

    def _drain_thread_sync(self, thread_id: str) -> List[Dict[str, Any]]:
        """Drain both Redis and local buffer for one thread."""
        return self._drain_redis_thread(thread_id) + self._drain_local_thread(thread_id)

    async def drain_thread_async(self, thread_id: str) -> List[Dict[str, Any]]:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._drain_thread_sync, thread_id)

    def drain_all(self) -> Dict[str, List[Dict[str, Any]]]:
        """Drain both Redis and local buffer for all threads."""
        result: Dict[str, List[Dict[str, Any]]] = {}

        # Redis
        client = self._get_client()
        if client is not None:
            try:
                keys = client.keys(f"{LOG_QUEUE_KEY_PREFIX}*")
                for key in keys:
                    tid = key[len(LOG_QUEUE_KEY_PREFIX):]
                    raw = client.lrange(key, 0, -1)
                    client.delete(key)
                    items = [json.loads(s) for s in raw if s]
                    if items:
                        result.setdefault(tid, []).extend(items)
            except Exception as e:
                print(f"[LOG_QUEUE] Redis drain_all failed: {e}")

        # Local fallback
        with self._local_lock:
            for tid, entries in self._local.items():
                if entries:
                    result.setdefault(tid, []).extend(entries)
            self._local.clear()

        return result

    async def drain_all_async(self) -> Dict[str, List[Dict[str, Any]]]:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.drain_all)

    # ------------------------------------------------------------------
    # Flush to DB (batch INSERT)
    # ------------------------------------------------------------------

    def flush_thread_to_db_sync(self, thread_id: str) -> int:
        """
        Drain this thread's queue (Redis + local) and INSERT into thread_logs
        in a single transaction. Returns number of rows inserted.
        """
        logs = self._drain_thread_sync(thread_id)
        if not logs:
            return 0
        try:
            from services.connection_pool import get_postgres_pool
            pool = get_postgres_pool()
        except (RuntimeError, ImportError):
            return 0
        try:
            conn = pool.getconn()
            try:
                return _insert_logs_batch(conn, {thread_id: logs})
            finally:
                pool.putconn(conn)
        except Exception as e:
            print(f"[LOG_QUEUE] flush_thread_to_db failed: {e}")
            return 0

    def flush_all_to_db_sync(self) -> int:
        """
        Drain all queued logs (Redis + local) and INSERT into thread_logs
        in a single transaction. Returns total rows inserted.
        """
        drained = self.drain_all()
        if not drained:
            return 0
        try:
            from services.connection_pool import get_postgres_pool
            pool = get_postgres_pool()
        except (RuntimeError, ImportError):
            return 0
        try:
            conn = pool.getconn()
            try:
                return _insert_logs_batch(conn, drained)
            finally:
                pool.putconn(conn)
        except Exception as e:
            print(f"[LOG_QUEUE] flush_all_to_db failed: {e}")
            return 0


# Singleton
_log_queue: Optional[RedisLogQueue] = None


def get_log_queue() -> RedisLogQueue:
    global _log_queue
    if _log_queue is None:
        _log_queue = RedisLogQueue()
    return _log_queue
