"""
Centralized connection pool manager for database connections.

This module provides a single source of truth for all database connections
to prevent connection exhaustion when running multiple services.

Features:
- Shared Postgres connection pool across all services
- MongoDB connection with configurable pool limits
- Connection monitoring and health checks
- Automatic retry and backoff for failed connections
- Thread-safe access patterns

Usage:
    from services.connection_pool import get_postgres_pool, get_mongo_client
    
    # Postgres (using context manager ensures return to pool)
    pool = get_postgres_pool()
    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM table")
    
    # MongoDB (connection pooling handled by driver)
    mongo = get_mongo_client()
    collection = mongo['database']['collection']
"""

import os
import logging
import threading
from contextlib import contextmanager
from typing import Optional, Dict, Any
from pathlib import Path

import psycopg
from psycopg_pool import ConnectionPool
from pymongo import MongoClient
from pymongo.errors import ServerSelectionTimeoutError

from env_loader import load_env_once

# Module-level logger
logger = logging.getLogger(__name__)

# Thread-safe singleton instances
_postgres_pool: Optional[ConnectionPool] = None
_mongo_client: Optional[MongoClient] = None
_pool_lock = threading.Lock()
_initialized = False

# Pool configuration
_DEFAULT_POSTGRES_CONFIG = {
    "min_size": 5,          # Minimum connections to maintain
    "max_size": 15,         # Maximum total connections (shared across all services)
    "max_waiting": 10,      # Max clients waiting for connection
    "timeout": 30.0,        # Timeout waiting for connection (seconds)
    "max_lifetime": 3600,   # Connection max lifetime (1 hour)
    "max_idle": 600,        # Max idle time before closing (10 minutes)
    "reconnect_timeout": 300.0,  # Timeout for reconnection attempts
}

_DEFAULT_MONGO_CONFIG = {
    "maxPoolSize": 20,      # Max connections per host
    "minPoolSize": 5,       # Min connections to maintain
    "maxIdleTimeMS": 300000,  # 5 minutes
    "waitQueueTimeoutMS": 30000,  # 30 seconds
    "serverSelectionTimeoutMS": 30000,  # 30 seconds
    "connectTimeoutMS": 20000,  # 20 seconds
    "socketTimeoutMS": 60000,  # 60 seconds for long queries
}


def _get_env_value(key: str, default: str = "") -> str:
    """Fetch an env var and fall back when unset or blank."""
    value = os.getenv(key)
    if value is None:
        return default
    value = value.strip()
    return value if value else default


def _get_postgres_config() -> Dict[str, Any]:
    """Get Postgres pool configuration from environment or defaults."""
    config = _DEFAULT_POSTGRES_CONFIG.copy()
    
    # Allow environment override
    if max_size := os.getenv("POSTGRES_POOL_MAX_SIZE"):
        config["max_size"] = int(max_size)
    if min_size := os.getenv("POSTGRES_POOL_MIN_SIZE"):
        config["min_size"] = int(min_size)
    if timeout := os.getenv("POSTGRES_POOL_TIMEOUT"):
        config["timeout"] = float(timeout)
    
    return config


def _get_mongo_config() -> Dict[str, Any]:
    """Get MongoDB connection configuration from environment or defaults."""
    config = _DEFAULT_MONGO_CONFIG.copy()
    
    # Allow environment override
    if max_pool := os.getenv("MONGO_MAX_POOL_SIZE"):
        config["maxPoolSize"] = int(max_pool)
    if min_pool := os.getenv("MONGO_MIN_POOL_SIZE"):
        config["minPoolSize"] = int(min_pool)
    
    return config


def initialize_pools(force: bool = False):
    """
    Initialize all database connection pools.
    
    Call this at application startup to ensure pools are ready.
    Thread-safe and idempotent (unless force=True).
    
    Args:
        force: If True, close and recreate existing pools
    """
    global _postgres_pool, _mongo_client, _initialized
    
    with _pool_lock:
        if _initialized and not force:
            logger.info("[CONNECTION_POOL] Already initialized, skipping")
            return
        
        # Close existing connections if forcing reinit
        if force:
            close_pools()
        
        # Load environment
        try:
            project_root = Path(__file__).resolve().parents[2]
            load_env_once(project_root)
        except Exception as e:
            logger.warning(f"[CONNECTION_POOL] Could not load env: {e}")
        
        # Initialize Postgres pool
        db_uri = _get_env_value("DATABASE_URL", "")
        if db_uri:
            try:
                config = _get_postgres_config()
                connection_kwargs = {
                    "autocommit": True,
                    "prepare_threshold": 0,
                }
                
                _postgres_pool = ConnectionPool(
                    conninfo=db_uri,
                    min_size=config["min_size"],
                    max_size=config["max_size"],
                    max_waiting=config["max_waiting"],
                    timeout=config["timeout"],
                    max_lifetime=config["max_lifetime"],
                    max_idle=config["max_idle"],
                    reconnect_timeout=config["reconnect_timeout"],
                    kwargs=connection_kwargs,
                    open=True,  # Open connections immediately
                )
                logger.info(
                    f"[CONNECTION_POOL] Postgres pool initialized: "
                    f"min={config['min_size']}, max={config['max_size']}"
                )
            except Exception as e:
                logger.error(f"[CONNECTION_POOL] Failed to initialize Postgres pool: {e}")
                _postgres_pool = None
        else:
            logger.warning("[CONNECTION_POOL] DATABASE_URL not set, Postgres pool disabled")
        
        # Initialize MongoDB client
        mongo_uri = _get_env_value("MONGODB_URI", "")
        if mongo_uri:
            try:
                config = _get_mongo_config()
                _mongo_client = MongoClient(mongo_uri, **config)
                
                # Test connection
                _mongo_client.admin.command('ping')
                
                logger.info(
                    f"[CONNECTION_POOL] MongoDB client initialized: "
                    f"maxPool={config['maxPoolSize']}, minPool={config['minPoolSize']}"
                )
            except ServerSelectionTimeoutError as e:
                logger.error(f"[CONNECTION_POOL] MongoDB connection failed: {e}")
                _mongo_client = None
            except Exception as e:
                logger.error(f"[CONNECTION_POOL] Failed to initialize MongoDB: {e}")
                _mongo_client = None
        else:
            logger.info("[CONNECTION_POOL] MONGODB_URI not set, MongoDB disabled")
        
        _initialized = True


def close_pools():
    """
    Close all connection pools gracefully.
    
    Call this at application shutdown to clean up resources.
    Thread-safe.
    """
    global _postgres_pool, _mongo_client, _initialized
    
    with _pool_lock:
        if _postgres_pool:
            try:
                _postgres_pool.close()
                logger.info("[CONNECTION_POOL] Postgres pool closed")
            except Exception as e:
                logger.error(f"[CONNECTION_POOL] Error closing Postgres pool: {e}")
            _postgres_pool = None
        
        if _mongo_client:
            try:
                _mongo_client.close()
                logger.info("[CONNECTION_POOL] MongoDB client closed")
            except Exception as e:
                logger.error(f"[CONNECTION_POOL] Error closing MongoDB client: {e}")
            _mongo_client = None
        
        _initialized = False


def get_postgres_pool() -> ConnectionPool:
    """
    Get the shared Postgres connection pool.
    
    Returns:
        ConnectionPool: The shared pool instance
    
    Raises:
        RuntimeError: If pool not initialized or DATABASE_URL not set
    
    Usage:
        pool = get_postgres_pool()
        with pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
    """
    if not _initialized:
        initialize_pools()
    
    if not _postgres_pool:
        raise RuntimeError(
            "Postgres connection pool not available. "
            "Ensure DATABASE_URL is set in environment."
        )
    
    return _postgres_pool


def get_mongo_client() -> MongoClient:
    """
    Get the shared MongoDB client.
    
    Returns:
        MongoClient: The shared client instance with connection pooling
    
    Raises:
        RuntimeError: If client not initialized or MONGODB_URI not set
    
    Usage:
        client = get_mongo_client()
        db = client['my_database']
        collection = db['my_collection']
        results = collection.find({"field": "value"})
    """
    if not _initialized:
        initialize_pools()
    
    if not _mongo_client:
        raise RuntimeError(
            "MongoDB client not available. "
            "Ensure MONGODB_URI is set in environment."
        )
    
    return _mongo_client


@contextmanager
def postgres_connection():
    """
    Context manager for Postgres connections from the pool.
    
    Automatically returns connection to pool on exit.
    
    Usage:
        with postgres_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM table")
                results = cur.fetchall()
    """
    pool = get_postgres_pool()
    conn = pool.getconn()
    try:
        yield conn
    finally:
        pool.putconn(conn)


def get_pool_stats() -> Dict[str, Any]:
    """
    Get current connection pool statistics for monitoring.
    
    Returns:
        Dict with pool stats including:
        - postgres_size: Current number of connections
        - postgres_available: Available connections
        - postgres_waiting: Clients waiting for connections
        - mongo_active: Active MongoDB connections (if available)
    """
    stats = {}
    
    with _pool_lock:
        if _postgres_pool:
            try:
                # Access pool statistics (psycopg_pool provides these)
                pool_stat = _postgres_pool.get_stats()
                stats["postgres_size"] = pool_stat.get("pool_size", 0)
                stats["postgres_available"] = pool_stat.get("pool_available", 0)
                stats["postgres_waiting"] = pool_stat.get("requests_waiting", 0)
                stats["postgres_healthy"] = True
            except Exception as e:
                logger.error(f"[CONNECTION_POOL] Error getting Postgres stats: {e}")
                stats["postgres_healthy"] = False
        
        if _mongo_client:
            try:
                # MongoDB doesn't expose detailed pool stats easily
                # But we can check if it's responsive
                _mongo_client.admin.command('ping', maxTimeMS=1000)
                stats["mongo_healthy"] = True
            except Exception as e:
                logger.error(f"[CONNECTION_POOL] MongoDB health check failed: {e}")
                stats["mongo_healthy"] = False
    
    return stats


def health_check() -> bool:
    """
    Perform health check on all connection pools.
    
    Returns:
        bool: True if all configured pools are healthy
    """
    try:
        stats = get_pool_stats()
        
        # Check Postgres if configured
        if _postgres_pool and not stats.get("postgres_healthy", False):
            return False
        
        # Check MongoDB if configured
        if _mongo_client and not stats.get("mongo_healthy", False):
            return False
        
        return True
    except Exception as e:
        logger.error(f"[CONNECTION_POOL] Health check failed: {e}")
        return False
