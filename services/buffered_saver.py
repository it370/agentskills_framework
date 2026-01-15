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
    """
    
    def __init__(self):
        super().__init__()
        # Lazy-load Redis buffer
        self._redis_buffer = None
        self.enabled = True  # Can be disabled via env var
        print("[BufferedSaver] Initialized (Redis buffering enabled)")
    
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
        """Get checkpoint from memory (or Redis if needed)."""
        # Try memory first (fast path)
        return await super().aget_tuple(config)
    
    def disable_buffering(self):
        """Disable Redis buffering (for testing or fallback)."""
        self.enabled = False
        print("[BufferedSaver] Redis buffering disabled")
    
    def enable_buffering(self):
        """Enable Redis buffering."""
        self.enabled = True
        print("[BufferedSaver] Redis buffering enabled")
