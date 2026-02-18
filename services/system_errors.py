"""
System error persistence utility.

This module provides functions to log critical system errors to the database
for admin investigation. These are separate from regular thread logs and are
meant for infrastructure/system-level failures that require admin attention.
"""

import asyncio
import traceback
from typing import Optional, Dict, Any
from datetime import datetime


async def log_system_error(
    error_type: str,
    severity: str,
    error_message: str,
    thread_id: Optional[str] = None,
    stack_trace: Optional[str] = None,
    error_context: Optional[Dict[str, Any]] = None,
    db_pool = None
) -> bool:
    """
    Log a critical system error to the database for admin investigation.
    
    Args:
        error_type: Category of error (e.g., 'checkpoint_flush_error', 'redis_error')
        severity: 'warning', 'error', or 'critical'
        error_message: Human-readable error message
        thread_id: Associated thread ID (if applicable)
        stack_trace: Full stack trace for debugging
        error_context: Additional context as JSON (checkpoint count, config, etc.)
        db_pool: PostgreSQL connection pool (if None, will fetch from connection_pool)
        
    Returns:
        bool: True if successful, False otherwise
    """
    def _log_sync():
        # Get connection pool
        nonlocal db_pool
        if db_pool is None:
            try:
                from services.connection_pool import get_postgres_pool
                db_pool = get_postgres_pool()
            except (RuntimeError, ImportError) as e:
                print(f"[SYSTEM_ERROR] Cannot get DB pool: {e}")
                return False
        
        try:
            import json
            conn = db_pool.getconn()
            try:
                with conn.cursor() as cur:
                    cur.execute("""
                        INSERT INTO system_errors 
                        (error_type, severity, thread_id, error_message, stack_trace, error_context, created_at)
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                        RETURNING id
                    """, (
                        error_type,
                        severity,
                        thread_id,
                        error_message,
                        stack_trace,
                        json.dumps(error_context) if error_context else None,
                        datetime.utcnow()
                    ))
                    error_id = cur.fetchone()[0]
                    conn.commit()
                    print(f"[SYSTEM_ERROR] Logged {severity} error (ID: {error_id}): {error_type}")
                    return True
            finally:
                db_pool.putconn(conn)
        except Exception as e:
            print(f"[SYSTEM_ERROR] Failed to log system error to DB: {e}")
            traceback.print_exc()
            return False
    
    try:
        return await asyncio.to_thread(_log_sync)
    except Exception as e:
        print(f"[SYSTEM_ERROR] Error in async wrapper: {e}")
        return False


async def log_checkpoint_flush_error(
    thread_id: str,
    error: Exception,
    checkpoint_count: int = 0,
    is_critical: bool = False
) -> bool:
    """
    Convenience function to log checkpoint flush errors.
    
    Args:
        thread_id: Thread that failed to flush
        error: The exception that occurred
        checkpoint_count: Number of checkpoints that failed to flush
        is_critical: Whether this is a critical error (exception) or warning (soft failure)
        
    Returns:
        bool: True if logged successfully
    """
    severity = "critical" if is_critical else "warning"
    error_message = str(error) if error else "Checkpoint flush returned False"
    stack_trace = "".join(traceback.format_exception(type(error), error, error.__traceback__)) if error else None
    
    error_context = {
        "checkpoint_count": checkpoint_count,
        "error_type": type(error).__name__ if error else "SoftFailure",
        "thread_id": thread_id
    }
    
    return await log_system_error(
        error_type="checkpoint_flush_error",
        severity=severity,
        error_message=error_message,
        thread_id=thread_id,
        stack_trace=stack_trace,
        error_context=error_context
    )


async def get_unresolved_errors(
    error_type: Optional[str] = None,
    severity: Optional[str] = None,
    limit: int = 100,
    db_pool = None
) -> list:
    """
    Retrieve unresolved system errors for admin dashboard.
    
    Args:
        error_type: Filter by error type (optional)
        severity: Filter by severity (optional)
        limit: Maximum number of errors to retrieve
        db_pool: PostgreSQL connection pool
        
    Returns:
        List of error dictionaries
    """
    def _get_sync():
        nonlocal db_pool
        if db_pool is None:
            try:
                from services.connection_pool import get_postgres_pool
                db_pool = get_postgres_pool()
            except (RuntimeError, ImportError):
                return []
        
        try:
            conn = db_pool.getconn()
            try:
                with conn.cursor() as cur:
                    query = """
                        SELECT id, error_type, severity, thread_id, error_message, 
                               stack_trace, error_context, created_at
                        FROM system_errors
                        WHERE resolved_at IS NULL
                    """
                    params = []
                    
                    if error_type:
                        query += " AND error_type = %s"
                        params.append(error_type)
                    
                    if severity:
                        query += " AND severity = %s"
                        params.append(severity)
                    
                    query += " ORDER BY created_at DESC LIMIT %s"
                    params.append(limit)
                    
                    cur.execute(query, params)
                    rows = cur.fetchall()
                    
                    return [
                        {
                            "id": row[0],
                            "error_type": row[1],
                            "severity": row[2],
                            "thread_id": row[3],
                            "error_message": row[4],
                            "stack_trace": row[5],
                            "error_context": row[6],
                            "created_at": row[7].isoformat() if row[7] else None
                        }
                        for row in rows
                    ]
            finally:
                db_pool.putconn(conn)
        except Exception as e:
            print(f"[SYSTEM_ERROR] Failed to retrieve errors: {e}")
            return []
    
    try:
        return await asyncio.to_thread(_get_sync)
    except Exception as e:
        print(f"[SYSTEM_ERROR] Error in async wrapper: {e}")
        return []


async def resolve_error(
    error_id: int,
    resolved_by: str,
    resolution_notes: Optional[str] = None,
    db_pool = None
) -> bool:
    """
    Mark a system error as resolved.
    
    Args:
        error_id: ID of the error to resolve
        resolved_by: Username/email of admin who resolved it
        resolution_notes: Optional notes about the resolution
        db_pool: PostgreSQL connection pool
        
    Returns:
        bool: True if successful
    """
    def _resolve_sync():
        nonlocal db_pool
        if db_pool is None:
            try:
                from services.connection_pool import get_postgres_pool
                db_pool = get_postgres_pool()
            except (RuntimeError, ImportError):
                return False
        
        try:
            conn = db_pool.getconn()
            try:
                with conn.cursor() as cur:
                    cur.execute("""
                        UPDATE system_errors
                        SET resolved_at = %s,
                            resolved_by = %s,
                            resolution_notes = %s
                        WHERE id = %s AND resolved_at IS NULL
                        RETURNING id
                    """, (datetime.utcnow(), resolved_by, resolution_notes, error_id))
                    
                    if cur.fetchone():
                        conn.commit()
                        print(f"[SYSTEM_ERROR] Resolved error ID {error_id} by {resolved_by}")
                        return True
                    else:
                        print(f"[SYSTEM_ERROR] Error ID {error_id} not found or already resolved")
                        return False
            finally:
                db_pool.putconn(conn)
        except Exception as e:
            print(f"[SYSTEM_ERROR] Failed to resolve error: {e}")
            return False
    
    try:
        return await asyncio.to_thread(_resolve_sync)
    except Exception as e:
        print(f"[SYSTEM_ERROR] Error in async wrapper: {e}")
        return False
