"""
Workflow UI event queue for SSE-path durability.

Primary backend: Redis (workflow_ui:queue:{thread_id}).
Fallback when Redis is unavailable: in-process dict keyed by thread_id.

Events are flushed to DB in batch at run-end and on app startup.
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

WORKFLOW_UI_QUEUE_KEY_PREFIX = "workflow_ui:queue:"


def _redis_params_from_env() -> Dict[str, Any]:
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


def _insert_events_batch(conn, events_by_thread: Dict[str, List[Dict[str, Any]]]) -> int:
    total = 0
    with conn.cursor() as cur:
        for thread_id, entries in events_by_thread.items():
            for entry in entries:
                event_id = str(entry.get("event_id") or "")
                parent_event_id = entry.get("parent_event_id")
                phase = entry.get("phase")
                node_kind = entry.get("node_kind")
                event_type = entry.get("type") or entry.get("event") or "workflow_ui_update"
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
                    INSERT INTO thread_workflow_ui_events
                    (thread_id, event_id, parent_event_id, phase, node_kind, event_type, payload, created_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb, %s)
                    ON CONFLICT (thread_id, event_id) DO NOTHING
                    """,
                    (
                        thread_id,
                        event_id,
                        str(parent_event_id) if parent_event_id is not None else None,
                        str(phase) if phase is not None else None,
                        str(node_kind) if node_kind is not None else None,
                        str(event_type),
                        json.dumps(entry),
                        created,
                    ),
                )
                total += 1
    conn.commit()
    return total


class RedisAdminEventQueue:
    def __init__(self):
        self._client: Optional["redis.Redis"] = None
        self._available: Optional[bool] = None
        self._local: Dict[str, List[Dict[str, Any]]] = {}
        self._local_lock = threading.Lock()

    def _key(self, thread_id: str) -> str:
        return f"{WORKFLOW_UI_QUEUE_KEY_PREFIX}{thread_id}"

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
            print("[WORKFLOW_UI_QUEUE] Connected to Redis for workflow UI events")
            return self._client
        except Exception as exc:
            print(f"[WORKFLOW_UI_QUEUE] Redis unavailable – using local fallback: {exc}")
            self._available = False
            self._client = None
            return None

    def push(self, thread_id: str, payload: Dict[str, Any]) -> bool:
        if not thread_id:
            return True
        client = self._get_client()
        if client is not None:
            try:
                client.rpush(self._key(thread_id), json.dumps(payload))
                return True
            except Exception as exc:
                print(f"[WORKFLOW_UI_QUEUE] Redis push failed, using local fallback: {exc}")
                self._available = False
                self._client = None
        with self._local_lock:
            self._local.setdefault(thread_id, []).append(payload)
        return True

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
        except Exception as exc:
            print(f"[WORKFLOW_UI_QUEUE] Redis drain_thread failed: {exc}")
            return []

    def _drain_local_thread(self, thread_id: str) -> List[Dict[str, Any]]:
        with self._local_lock:
            return self._local.pop(thread_id, [])

    def _drain_thread_sync(self, thread_id: str) -> List[Dict[str, Any]]:
        return self._drain_redis_thread(thread_id) + self._drain_local_thread(thread_id)

    def drain_all(self) -> Dict[str, List[Dict[str, Any]]]:
        result: Dict[str, List[Dict[str, Any]]] = {}
        client = self._get_client()
        if client is not None:
            try:
                keys = client.keys(f"{WORKFLOW_UI_QUEUE_KEY_PREFIX}*")
                for key in keys:
                    tid = key[len(WORKFLOW_UI_QUEUE_KEY_PREFIX):]
                    raw = client.lrange(key, 0, -1)
                    client.delete(key)
                    items = [json.loads(s) for s in raw if s]
                    if items:
                        result.setdefault(tid, []).extend(items)
            except Exception as exc:
                print(f"[WORKFLOW_UI_QUEUE] Redis drain_all failed: {exc}")
        with self._local_lock:
            for tid, entries in self._local.items():
                if entries:
                    result.setdefault(tid, []).extend(entries)
            self._local.clear()
        return result

    def flush_thread_to_db_sync(self, thread_id: str) -> int:
        events = self._drain_thread_sync(thread_id)
        if not events:
            return 0
        try:
            from services.connection_pool import get_postgres_pool
            pool = get_postgres_pool()
        except (RuntimeError, ImportError):
            return 0
        try:
            conn = pool.getconn()
            try:
                return _insert_events_batch(conn, {thread_id: events})
            finally:
                pool.putconn(conn)
        except Exception as exc:
            print(f"[WORKFLOW_UI_QUEUE] flush_thread_to_db failed: {exc}")
            return 0

    def flush_all_to_db_sync(self) -> int:
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
                return _insert_events_batch(conn, drained)
            finally:
                pool.putconn(conn)
        except Exception as exc:
            print(f"[WORKFLOW_UI_QUEUE] flush_all_to_db failed: {exc}")
            return 0


_admin_event_queue: Optional[RedisAdminEventQueue] = None


def get_admin_event_queue() -> RedisAdminEventQueue:
    global _admin_event_queue
    if _admin_event_queue is None:
        _admin_event_queue = RedisAdminEventQueue()
    return _admin_event_queue


def get_thread_workflow_ui_events_sync(thread_id: str, limit: int = 2000) -> List[Dict[str, Any]]:
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
                    SELECT payload
                    FROM thread_workflow_ui_events
                    WHERE thread_id = %s
                    ORDER BY created_at ASC, id ASC
                    LIMIT %s
                    """,
                    (thread_id, limit),
                )
                rows = cur.fetchall()
                return [row[0] for row in rows if row and row[0] is not None]
        finally:
            pool.putconn(conn)
    except Exception as exc:
        print(f"[WORKFLOW_UI_QUEUE] Failed to load persisted workflow_ui events: {exc}")
        return []


async def get_thread_workflow_ui_events(thread_id: str, limit: int = 2000) -> List[Dict[str, Any]]:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, get_thread_workflow_ui_events_sync, thread_id, limit)
