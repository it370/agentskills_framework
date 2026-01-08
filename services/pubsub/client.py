"""
Pub/Sub client abstraction for event broadcasting.
Supports both Redis and PostgreSQL backends.
"""

import json
import os
from abc import ABC, abstractmethod
from typing import Any, Dict, Callable, Optional
from threading import Event
import time


class PubSubClient(ABC):
    """Abstract base class for pub/sub implementations."""
    
    @abstractmethod
    def publish(self, channel: str, message: Dict[str, Any]) -> bool:
        """
        Publish a message to a channel.
        
        Args:
            channel: Channel name
            message: Message payload (will be JSON serialized)
            
        Returns:
            True if successful, False otherwise
        """
        pass
    
    @abstractmethod
    def listen(self, channel: str, callback: Callable[[Dict[str, Any]], None], stop_flag: Event):
        """
        Listen for messages on a channel (blocking).
        
        Args:
            channel: Channel name to subscribe to
            callback: Function to call when message received
            stop_flag: Threading Event to signal stop
        """
        pass
    
    @abstractmethod
    def close(self):
        """Close connections and cleanup resources."""
        pass


class PostgresPubSubClient(PubSubClient):
    """PostgreSQL NOTIFY/LISTEN implementation."""
    
    def __init__(self, connection_string: str):
        """
        Initialize PostgreSQL pub/sub client.
        
        Args:
            connection_string: PostgreSQL connection string
        """
        self.connection_string = connection_string
        self._conn = None
        
    def _get_connection(self):
        """Lazy connection initialization."""
        if self._conn is None:
            from psycopg import Connection as SyncConnection
            self._conn = SyncConnection.connect(self.connection_string, autocommit=True)
        return self._conn
    
    def publish(self, channel: str, message: Dict[str, Any]) -> bool:
        """Publish via pg_notify."""
        try:
            conn = self._get_connection()
            with conn.cursor() as cur:
                cur.execute("SELECT pg_notify(%s, %s)", (channel, json.dumps(message)))
            return True
        except Exception as e:
            print(f"[PubSub] PostgreSQL publish failed: {e}")
            return False
    
    def listen(self, channel: str, callback: Callable[[Dict[str, Any]], None], stop_flag: Event):
        """Listen via LISTEN command with polling."""
        try:
            conn = self._get_connection()
            conn.execute(f"LISTEN {channel}")
            print(f"[PubSub] Listening on PostgreSQL channel: {channel}")
            
            # Set a shorter timeout for connection
            conn.execute("SET statement_timeout = '100ms'")
            
            while not stop_flag.is_set():
                try:
                    # Keep-alive query with shorter timeout
                    conn.execute("SELECT 1")
                    
                    # Process any notifications
                    for notify in conn.notifies():
                        try:
                            payload = json.loads(notify.payload)
                        except Exception:
                            payload = {"raw": notify.payload}
                        callback(payload)
                except Exception:
                    # Ignore timeout errors during shutdown
                    if stop_flag.is_set():
                        break
                
                # Sleep briefly to allow quick shutdown
                time.sleep(0.1)
            
            print(f"[PubSub] Stopped listening on PostgreSQL channel: {channel}")
        except Exception as e:
            if not stop_flag.is_set():
                print(f"[PubSub] PostgreSQL listen error: {e}")
    
    def close(self):
        """Close PostgreSQL connection."""
        if self._conn:
            self._conn.close()
            self._conn = None


class RedisPubSubClient(PubSubClient):
    """Redis Pub/Sub implementation."""
    
    def __init__(
        self, 
        host: str = 'localhost',
        port: int = 6379,
        db: int = 0,
        username: Optional[str] = None,
        password: Optional[str] = None,
        connection_string: Optional[str] = None
    ):
        """
        Initialize Redis pub/sub client.
        
        Args:
            host: Redis host
            port: Redis port
            db: Redis database number
            username: Redis username (optional)
            password: Redis password (optional)
            connection_string: Redis URL (if provided, overrides other params)
        """
        self.connection_string = connection_string
        self.host = host
        self.port = port
        self.db = db
        self.username = username
        self.password = password
        self._redis = None
        self._pubsub = None
        
    def _get_redis(self):
        """Lazy connection initialization."""
        if self._redis is None:
            import redis
            
            if self.connection_string:
                # Use connection string if provided
                self._redis = redis.from_url(self.connection_string, decode_responses=True)
            else:
                # Use separate parameters
                self._redis = redis.Redis(
                    host=self.host,
                    port=self.port,
                    db=self.db,
                    username=self.username,
                    password=self.password,
                    decode_responses=True
                )
        return self._redis
    
    def publish(self, channel: str, message: Dict[str, Any]) -> bool:
        """Publish via Redis PUBLISH."""
        try:
            redis_client = self._get_redis()
            redis_client.publish(channel, json.dumps(message))
            return True
        except Exception as e:
            print(f"[PubSub] Redis publish failed: {e}")
            return False
    
    def listen(self, channel: str, callback: Callable[[Dict[str, Any]], None], stop_flag: Event):
        """Listen via Redis SUBSCRIBE with timeout for quick shutdown."""
        try:
            redis_client = self._get_redis()
            self._pubsub = redis_client.pubsub()
            self._pubsub.subscribe(channel)
            print(f"[PubSub] Listening on Redis channel: {channel}")
            
            # Use get_message with timeout instead of blocking listen
            while not stop_flag.is_set():
                try:
                    # Check for messages with timeout to allow quick shutdown
                    message = self._pubsub.get_message(timeout=0.1)
                    
                    if message and message['type'] == 'message':
                        try:
                            payload = json.loads(message['data'])
                        except Exception:
                            payload = {"raw": message['data']}
                        callback(payload)
                except Exception as e:
                    # Ignore timeout/shutdown errors
                    if not stop_flag.is_set():
                        print(f"[PubSub] Redis message error: {e}")
                    break
            
            print(f"[PubSub] Stopped listening on Redis channel: {channel}")
        except Exception as e:
            if not stop_flag.is_set():
                print(f"[PubSub] Redis listen error: {e}")
        finally:
            if self._pubsub:
                try:
                    self._pubsub.unsubscribe(channel)
                    self._pubsub.close()
                except Exception:
                    pass  # Ignore errors during cleanup
    
    def close(self):
        """Close Redis connections."""
        if self._pubsub:
            self._pubsub.close()
            self._pubsub = None
        if self._redis:
            self._redis.close()
            self._redis = None


def create_pubsub_client(backend: Optional[str] = None, connection_string: Optional[str] = None) -> PubSubClient:
    """
    Factory function to create appropriate pub/sub client.
    
    Args:
        backend: 'redis' or 'postgres'. If None, reads from PUBSUB_BACKEND env var.
        connection_string: Connection string. If None, reads from appropriate env vars.
        
    Returns:
        PubSubClient instance
        
    Environment Variables:
        PUBSUB_BACKEND: 'redis' or 'postgres' (default: 'postgres')
        
        For PostgreSQL:
          DATABASE_URL: PostgreSQL connection string
        
        For Redis (option 1 - connection string):
          REDIS_URL: Redis connection string (redis://host:port/db)
        
        For Redis (option 2 - separate parameters):
          REDIS_HOST: Redis host (default: localhost)
          REDIS_PORT: Redis port (default: 6379)
          REDIS_DB: Redis database number (default: 0)
          REDIS_USERNAME: Redis username (optional)
          REDIS_PASSWORD: Redis password (optional)
    """
    # Determine backend
    if backend is None:
        backend = os.getenv('PUBSUB_BACKEND', 'postgres').lower()
    
    # Get connection string or parameters
    if backend == 'redis':
        try:
            import redis  # Check if redis is available
            
            # Check if connection string is provided
            if connection_string is None:
                connection_string = os.getenv('REDIS_URL', '')
            
            # If no connection string, use separate parameters
            if not connection_string:
                redis_host = os.getenv('REDIS_HOST', 'localhost')
                redis_port = int(os.getenv('REDIS_PORT', '6379'))
                redis_db = int(os.getenv('REDIS_DB', '0'))
                redis_username = os.getenv('REDIS_USERNAME', None)
                redis_password = os.getenv('REDIS_PASSWORD', None)
                
                return RedisPubSubClient(
                    host=redis_host,
                    port=redis_port,
                    db=redis_db,
                    username=redis_username,
                    password=redis_password
                )
            else:
                return RedisPubSubClient(connection_string=connection_string)
                
        except ImportError:
            print("[PubSub] Redis not available, falling back to PostgreSQL")
            backend = 'postgres'
            connection_string = os.getenv('DATABASE_URL', '')
    
    if backend == 'postgres':
        if connection_string is None:
            connection_string = os.getenv('DATABASE_URL', '')
            if not connection_string:
                raise ValueError("DATABASE_URL not set for PostgreSQL pub/sub")
        return PostgresPubSubClient(connection_string)
    
    raise ValueError(f"Unknown pub/sub backend: {backend}")


# Convenience singleton for the application
_default_client: Optional[PubSubClient] = None


def get_default_client() -> PubSubClient:
    """Get or create the default pub/sub client."""
    global _default_client
    if _default_client is None:
        _default_client = create_pubsub_client()
    return _default_client


def set_default_client(client: PubSubClient):
    """Set a custom default client."""
    global _default_client
    _default_client = client

