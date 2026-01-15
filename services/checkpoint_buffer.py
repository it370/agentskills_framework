"""
Redis-based checkpoint buffering for high-performance execution.

During workflow execution:
- Checkpoints stored in Redis with 30-minute TTL (extended on each write)
- Fast writes, no PostgreSQL bottleneck

On workflow completion/error:
- Batch flush all checkpoints to PostgreSQL for persistence
- Cleanup Redis buffer

Features:
- Automatic TTL extension on each checkpoint
- Batch PostgreSQL writes
- Startup recovery for crashed workflows
"""

import os
import json
import asyncio
from typing import List, Dict, Any, Optional
from datetime import datetime

# Use sync Redis client
import redis


class RedisCheckpointBuffer:
    """Manages checkpoint buffering in Redis with automatic TTL extension."""
    
    def __init__(self):
        self.redis_host = os.getenv("REDIS_HOST", "localhost")
        
        # Parse Redis port with error handling
        try:
            self.redis_port = int(os.getenv("REDIS_PORT", "6379"))
        except (ValueError, TypeError):
            print(f"[CheckpointBuffer] WARNING: Invalid REDIS_PORT, using default 6379")
            self.redis_port = 6379
        
        # Parse Redis DB
        # For Redis Cloud: database name is in the endpoint, db param should be ignored
        # For OSS Redis: db is a number (0-15)
        redis_db_str = os.getenv("REDIS_DB", "0")
        try:
            self.redis_db = int(redis_db_str)
            self.use_db_param = True
        except (ValueError, TypeError):
            # Named database (Redis Cloud) - database selection is via endpoint, not db param
            print(f"[CheckpointBuffer] Using Redis Cloud with database: {redis_db_str}")
            self.redis_db = 0  # Ignored for Redis Cloud
            self.use_db_param = False
        
        self.redis_password = os.getenv("REDIS_PASSWORD", None) or None
        
        # 30 minutes TTL, extended on each write
        self.ttl_seconds = 1800
        
        # Connection pool (will be lazy-initialized)
        self._redis_client = None
    
    def _get_client(self):
        """Get or create Redis client."""
        if self._redis_client is None:
            try:
                # Build connection params
                conn_params = {
                    "host": self.redis_host,
                    "port": self.redis_port,
                    "password": self.redis_password,
                    "decode_responses": True,
                    "socket_connect_timeout": 5,
                    "socket_timeout": 5
                }
                
                # Only add db param for OSS Redis (numbered databases)
                if self.use_db_param:
                    conn_params["db"] = self.redis_db
                
                self._redis_client = redis.Redis(**conn_params)
                
                # Test connection
                self._redis_client.ping()
                print(f"[CheckpointBuffer] Connected to Redis at {self.redis_host}:{self.redis_port}")
            except Exception as e:
                print(f"[CheckpointBuffer] ERROR: Cannot connect to Redis: {e}")
                self._redis_client = None
                raise
        return self._redis_client
    
    def _checkpoint_key(self, thread_id: str) -> str:
        """Get Redis key for thread checkpoints."""
        return f"checkpoints:{thread_id}"
    
    async def add_checkpoint(self, thread_id: str, checkpoint_data: Dict[str, Any]) -> bool:
        """
        Add checkpoint to Redis buffer.
        
        Args:
            thread_id: Thread identifier
            checkpoint_data: Full checkpoint data including config, checkpoint, metadata
            
        Returns:
            bool: True if successful
        """
        def _add_sync():
            client = self._get_client()
            if not client:
                return False
            
            key = self._checkpoint_key(thread_id)
            
            # Serialize checkpoint
            checkpoint_json = json.dumps(checkpoint_data)
            
            # Add to list
            client.rpush(key, checkpoint_json)
            
            # Extend TTL on each write (incremental)
            client.expire(key, self.ttl_seconds)
            
            # Get count for logging
            count = client.llen(key)
            print(f"[CheckpointBuffer] Added checkpoint #{count} for {thread_id} (TTL: 30min)")
            
            return True
        
        try:
            return await asyncio.to_thread(_add_sync)
        except Exception as e:
            print(f"[CheckpointBuffer] ERROR: Failed to add checkpoint for {thread_id}: {e}")
            return False
    
    async def get_all_checkpoints(self, thread_id: str) -> List[Dict[str, Any]]:
        """
        Get all buffered checkpoints for a thread.
        
        Args:
            thread_id: Thread identifier
            
        Returns:
            List of checkpoint data dicts
        """
        def _get_sync():
            client = self._get_client()
            if not client:
                return []
            
            key = self._checkpoint_key(thread_id)
            
            # Get entire list
            checkpoint_jsons = client.lrange(key, 0, -1)
            
            if not checkpoint_jsons:
                return []
            
            # Deserialize all checkpoints
            checkpoints = [json.loads(cp) for cp in checkpoint_jsons]
            print(f"[CheckpointBuffer] Retrieved {len(checkpoints)} checkpoints for {thread_id}")
            
            return checkpoints
        
        try:
            return await asyncio.to_thread(_get_sync)
        except Exception as e:
            print(f"[CheckpointBuffer] ERROR: Failed to get checkpoints for {thread_id}: {e}")
            return []
    
    async def flush_to_postgres(self, thread_id: str, db_uri: str) -> bool:
        """
        Batch write all checkpoints to PostgreSQL and cleanup Redis.
        
        Args:
            thread_id: Thread identifier
            db_uri: PostgreSQL connection string (e.g., postgresql://user:pass@host:port/dbname)
            
        Returns:
            bool: True if successful
        """
        try:
            checkpoints = await self.get_all_checkpoints(thread_id)
            
            if not checkpoints:
                print(f"[CheckpointBuffer] No checkpoints to flush for {thread_id}")
                return True
            
            # Validate db_uri format
            if not db_uri or not db_uri.startswith(('postgresql://', 'postgres://')):
                print(f"[CheckpointBuffer] ERROR: Invalid DATABASE_URL format: {db_uri[:50]}...")
                return False
            
            # Write to PostgreSQL in blocking thread
            def _write_sync():
                import psycopg
                with psycopg.connect(db_uri, autocommit=True) as conn:
                    with conn.cursor() as cur:
                        for checkpoint_data in checkpoints:
                            config = checkpoint_data.get('config', {})
                            checkpoint = checkpoint_data.get('checkpoint', {})
                            metadata = checkpoint_data.get('metadata', {})
                            parent_config = checkpoint_data.get('parent_config')
                            
                            # Extract identifiers
                            checkpoint_ns = config.get('configurable', {}).get('checkpoint_ns', '')
                            checkpoint_id = checkpoint.get('id', '')
                            
                            cur.execute("""
                                INSERT INTO checkpoints 
                                (thread_id, checkpoint_ns, checkpoint_id, parent_checkpoint_id, type, checkpoint, metadata)
                                VALUES (%s, %s, %s, %s, %s, %s, %s)
                                ON CONFLICT (thread_id, checkpoint_ns, checkpoint_id) 
                                DO UPDATE SET
                                    checkpoint = EXCLUDED.checkpoint,
                                    metadata = EXCLUDED.metadata
                            """, (
                                thread_id,
                                checkpoint_ns,
                                checkpoint_id,
                                parent_config.get('configurable', {}).get('checkpoint_id') if parent_config else None,
                                'checkpoint',
                                json.dumps(checkpoint),
                                json.dumps(metadata)
                            ))
            
            # Execute in thread pool
            await asyncio.to_thread(_write_sync)
            
            # Delete from Redis after successful write
            def _delete_sync():
                client = self._get_client()
                if client:
                    key = self._checkpoint_key(thread_id)
                    client.delete(key)
            
            await asyncio.to_thread(_delete_sync)
            
            print(f"[CheckpointBuffer] ✅ Flushed {len(checkpoints)} checkpoints to PostgreSQL for {thread_id}")
            return True
            
        except Exception as e:
            print(f"[CheckpointBuffer] ERROR: Failed to flush checkpoints for {thread_id}: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    async def cleanup_thread(self, thread_id: str):
        """Delete buffered checkpoints for a thread (without flushing)."""
        def _cleanup_sync():
            client = self._get_client()
            if client:
                key = self._checkpoint_key(thread_id)
                client.delete(key)
                print(f"[CheckpointBuffer] Cleaned up buffer for {thread_id}")
        
        try:
            await asyncio.to_thread(_cleanup_sync)
        except Exception as e:
            print(f"[CheckpointBuffer] ERROR: Failed to cleanup {thread_id}: {e}")
    
    async def get_all_buffered_threads(self) -> List[str]:
        """Get list of all threads with buffered checkpoints."""
        def _scan_sync():
            client = self._get_client()
            if not client:
                return []
            
            keys = []
            for key in client.scan_iter("checkpoints:*"):
                thread_id = key.replace("checkpoints:", "")
                keys.append(thread_id)
            return keys
        
        try:
            return await asyncio.to_thread(_scan_sync)
        except Exception as e:
            print(f"[CheckpointBuffer] ERROR: Failed to scan keys: {e}")
            return []
    
    async def close(self):
        """Close Redis connection."""
        def _close_sync():
            if self._redis_client:
                self._redis_client.close()
        
        try:
            await asyncio.to_thread(_close_sync)
        except Exception as e:
            print(f"[CheckpointBuffer] ERROR closing connection: {e}")


async def recover_buffered_checkpoints(db_uri: str):
    """
    Startup recovery: Flush any remaining checkpoints from Redis to PostgreSQL.
    
    Should be called on server startup to recover checkpoints from crashed workflows.
    """
    buffer = RedisCheckpointBuffer()
    
    try:
        threads = await buffer.get_all_buffered_threads()
        
        if not threads:
            print("[CheckpointBuffer] No buffered checkpoints to recover")
            return
        
        print(f"[CheckpointBuffer] Recovering {len(threads)} buffered thread(s)...")
        
        for thread_id in threads:
            try:
                success = await buffer.flush_to_postgres(thread_id, db_uri)
                if success:
                    print(f"[CheckpointBuffer] ✅ Recovered {thread_id}")
                else:
                    print(f"[CheckpointBuffer] ❌ Failed to recover {thread_id}")
            except Exception as e:
                print(f"[CheckpointBuffer] ERROR recovering {thread_id}: {e}")
        
        print("[CheckpointBuffer] Recovery complete")
        
    except Exception as e:
        print(f"[CheckpointBuffer] ERROR during recovery: {e}")
    finally:
        await buffer.close()
