"""
Buffered Checkpoint Saver

Combines in-memory execution with Redis buffering for optimal performance:
- MemorySaver: Fast in-memory access during workflow execution
- Redis: Persistent buffer with 30-min TTL for recovery
- PostgreSQL: Final persistent storage on completion

This avoids PostgreSQL bottlenecks during execution while maintaining persistence.
"""

from typing import Optional, Any, Dict
from langgraph.checkpoint.memory import MemorySaver
from langgraph.checkpoint.base import Checkpoint, CheckpointMetadata, CheckpointTuple


class BufferedCheckpointSaver(MemorySaver):
    """
    Checkpoint saver that buffers to Redis while using memory for active execution.
    
    Write path:
        1. Write to memory (fast, for immediate access)
        2. Buffer to Redis (async, for persistence)
    
    Read path:
        - Read from memory (fast)
        - Fallback to Redis if not in memory (recovery scenarios)
        - Fallback to PostgreSQL for completed runs
    
    Memory is cleared after flush to PostgreSQL to prevent memory leaks.
    """
    
    def __init__(self):
        super().__init__()
        # Lazy-load Redis buffer
        self._redis_buffer = None
        self.enabled = True  # Can be disabled via env var
        print("[BufferedSaver] Initialized (Redis buffering enabled)")
    
    def clear_thread_memory(self, thread_id: str):
        """
        Clear memory for a SPECIFIC thread after it's been flushed to PostgreSQL.
        This prevents memory leaks from accumulating completed workflows.
        
        SAFETY: Only clears checkpoints for the exact thread_id specified.
        Does NOT affect other concurrent workflows from other users or threads.
        """
        if not thread_id or not isinstance(thread_id, str):
            print(f"[BufferedSaver] ERROR: Invalid thread_id for memory clear: {thread_id}")
            return
        
        try:
            # Access the internal storage dict from MemorySaver
            # MemorySaver stores checkpoints keyed by (thread_id, checkpoint_ns, checkpoint_id)
            # We ONLY remove keys where key[0] matches the exact thread_id
            keys_to_remove = []
            for key in list(self.storage.keys()):  # Create list copy for safe iteration
                # Verify key structure and match thread_id
                if isinstance(key, tuple) and len(key) >= 1 and key[0] == thread_id:
                    keys_to_remove.append(key)
            
            # Remove only the matched keys
            for key in keys_to_remove:
                del self.storage[key]
            
            if keys_to_remove:
                print(f"[BufferedSaver] ✅ Cleared {len(keys_to_remove)} checkpoint(s) from memory for thread {thread_id}")
            else:
                print(f"[BufferedSaver] No checkpoints found in memory for thread {thread_id}")
        except Exception as e:
            print(f"[BufferedSaver] ERROR clearing memory for thread {thread_id}: {e}")
            import traceback
            traceback.print_exc()
    
    def _get_redis_buffer(self):
        """Lazy-initialize Redis buffer."""
        if self._redis_buffer is None:
            try:
                from services.checkpoint_buffer import RedisCheckpointBuffer
                self._redis_buffer = RedisCheckpointBuffer()
                print("[BufferedSaver] Redis buffer connected")
            except Exception as e:
                print(f"[BufferedSaver] Failed to connect to Redis: {e}")
                self.enabled = False
        return self._redis_buffer
        
    async def aput(
        self,
        config: Dict[str, Any],
        checkpoint: Checkpoint,
        metadata: CheckpointMetadata,
        new_versions: Optional[Any] = None,
    ) -> Dict[str, Any]:
        """Save checkpoint to memory and buffer to Redis."""
        
        # Always save to memory first (for active execution)
        result = await super().aput(config, checkpoint, metadata, new_versions)
        
        # Buffer to Redis if enabled
        if self.enabled:
            thread_id = config.get("configurable", {}).get("thread_id")
            if thread_id:
                try:
                    redis_buffer = self._get_redis_buffer()
                    if redis_buffer:
                        # Serialize ALL checkpoint data (config, checkpoint, metadata)
                        checkpoint_data = self._make_json_serializable({
                            "config": config,
                            "checkpoint": self._serialize_checkpoint(checkpoint),
                            "metadata": metadata,
                            "parent_config": config.get("configurable", {}).get("checkpoint_id")
                        })
                        await redis_buffer.add_checkpoint(thread_id, checkpoint_data)
                except Exception as e:
                    print(f"[BufferedSaver] ERROR buffering checkpoint: {e}")
        
        return result
    
    def _serialize_checkpoint(self, checkpoint: Checkpoint) -> dict:
        """Convert Checkpoint object to JSON-serializable dict."""
        if isinstance(checkpoint, dict):
            return self._make_json_serializable(checkpoint)
        
        # Convert Checkpoint object to dict
        return self._make_json_serializable({
            "v": getattr(checkpoint, "v", 1),
            "id": getattr(checkpoint, "id", ""),
            "ts": getattr(checkpoint, "ts", ""),
            "channel_values": getattr(checkpoint, "channel_values", {}),
            "channel_versions": getattr(checkpoint, "channel_versions", {}),
            "versions_seen": getattr(checkpoint, "versions_seen", {}),
            "pending_sends": getattr(checkpoint, "pending_sends", []),
        })
    
    def _make_json_serializable(self, obj):
        """Recursively convert objects to JSON-serializable types."""
        from collections.abc import Mapping
        from collections import ChainMap
        
        if isinstance(obj, ChainMap):
            # Convert ChainMap to regular dict
            return self._make_json_serializable(dict(obj))
        elif isinstance(obj, dict):
            # Recursively serialize dict values
            return {k: self._make_json_serializable(v) for k, v in obj.items()}
        elif isinstance(obj, (list, tuple)):
            # Recursively serialize list/tuple items
            return [self._make_json_serializable(item) for item in obj]
        elif isinstance(obj, (str, int, float, bool, type(None))):
            # Already serializable
            return obj
        else:
            # Try to convert to dict, fallback to string representation
            try:
                if isinstance(obj, Mapping):
                    return self._make_json_serializable(dict(obj))
                else:
                    return str(obj)
            except:
                return str(obj)
    
    async def aget_tuple(self, config: Dict[str, Any]) -> Optional[CheckpointTuple]:
        """
        Get checkpoint from memory, Redis, or PostgreSQL (in that order).
        
        Read hierarchy:
        1. Memory (fast, for same-process access during execution)
        2. Redis (for cross-process/server access during execution)
        3. PostgreSQL (for completed runs after Redis flush)
        """
        # Try memory first (fast path)
        memory_tuple = await super().aget_tuple(config)
        if memory_tuple is not None:
            return memory_tuple
        
        thread_id = config.get("configurable", {}).get("thread_id")
        if not thread_id:
            return None
        
        # Fallback #1: Redis (for active runs on different processes/servers)
        if self.enabled:
            try:
                redis_buffer = self._get_redis_buffer()
                if redis_buffer:
                    checkpoints = await redis_buffer.get_all_checkpoints(thread_id)
                    if checkpoints:
                        # Get the latest checkpoint (last in list)
                        latest = checkpoints[-1]
                        return self._reconstruct_checkpoint_tuple(latest, config)
            except Exception as e:
                print(f"[BufferedSaver] ERROR reading from Redis: {e}")
        
        # Fallback #2: PostgreSQL (for completed runs)
        try:
            import asyncio
            from engine import _get_env_value
            
            db_uri = _get_env_value("DATABASE_URL", "")
            if not db_uri:
                return None
            
            def _read_from_postgres():
                import psycopg
                import json
                with psycopg.connect(db_uri) as conn:
                    with conn.cursor() as cur:
                        # Get the latest checkpoint for this thread
                        cur.execute("""
                            SELECT checkpoint, metadata, parent_checkpoint_id
                            FROM checkpoints
                            WHERE thread_id = %s
                            ORDER BY checkpoint_id DESC
                            LIMIT 1
                        """, (thread_id,))
                        row = cur.fetchone()
                        if row:
                            return {
                                "checkpoint": json.loads(row[0]) if isinstance(row[0], str) else row[0],
                                "metadata": json.loads(row[1]) if isinstance(row[1], str) else row[1],
                                "parent_config": row[2]
                            }
                return None
            
            pg_data = await asyncio.to_thread(_read_from_postgres)
            if pg_data:
                return self._reconstruct_checkpoint_tuple(pg_data, config)
                
        except Exception as e:
            print(f"[BufferedSaver] ERROR reading from PostgreSQL: {e}")
        
        return None
    
    def _reconstruct_checkpoint_tuple(self, data: Dict[str, Any], config: Dict[str, Any]) -> CheckpointTuple:
        """Reconstruct CheckpointTuple from serialized data."""
        checkpoint_data = data.get("checkpoint", {})
        metadata = data.get("metadata", {})
        parent_config = data.get("parent_config")
        
        # Convert dict back to Checkpoint object
        from langgraph.checkpoint.base import Checkpoint
        checkpoint = Checkpoint(
            v=checkpoint_data.get("v", 1),
            id=checkpoint_data.get("id", ""),
            ts=checkpoint_data.get("ts", ""),
            channel_values=checkpoint_data.get("channel_values", {}),
            channel_versions=checkpoint_data.get("channel_versions", {}),
            versions_seen=checkpoint_data.get("versions_seen", {}),
            pending_sends=checkpoint_data.get("pending_sends", [])
        )
        
        # Build parent config if available
        parent_cfg = None
        if parent_config:
            parent_cfg = {"configurable": {"checkpoint_id": parent_config}}
        
        return CheckpointTuple(
            config=config,
            checkpoint=checkpoint,
            metadata=metadata,
            parent_config=parent_cfg
        )
    
    def disable_buffering(self):
        """Disable Redis buffering (for testing or fallback)."""
        self.enabled = False
        print("[BufferedSaver] Redis buffering disabled")
    
    def enable_buffering(self):
        """Enable Redis buffering."""
        self.enabled = True
        print("[BufferedSaver] Redis buffering enabled")
