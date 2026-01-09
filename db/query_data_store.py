#!/usr/bin/env python3
"""
Query and display data_store from checkpoints database.

This script shows how to extract the actual data_store values from LangGraph's
checkpoint storage, which uses msgpack binary serialization.

Nelvin Note: This is for testing db values. Dev Usage only
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from env_loader import load_env_once
import psycopg
import json

try:
    import msgpack
except ImportError:
    print("ERROR: msgpack library required")
    print("Install with: pip install msgpack")
    sys.exit(1)

def get_data_store(thread_id: str):
    """Get the current data_store for a specific thread."""
    
    load_env_once(Path(__file__).resolve().parents[1])
    db_uri = os.getenv("DATABASE_URL")
    
    if not db_uri:
        print("ERROR: DATABASE_URL not set")
        return None
    
    try:
        with psycopg.connect(db_uri, autocommit=True) as conn:
            with conn.cursor() as cur:
                # Get the data_store version reference from latest checkpoint
                cur.execute("""
                    SELECT 
                        checkpoint_id,
                        checkpoint->'channel_versions'->>'data_store' as data_store_version
                    FROM checkpoints
                    WHERE thread_id = %s
                      AND checkpoint_ns = ''
                    ORDER BY (checkpoint->>'ts')::timestamp DESC
                    LIMIT 1
                """, (thread_id,))
                
                result = cur.fetchone()
                if not result:
                    print(f"No checkpoint found for thread: {thread_id}")
                    return None
                
                checkpoint_id, data_store_version = result
                print(f"Thread ID: {thread_id}")
                print(f"Checkpoint ID: {checkpoint_id}")
                print(f"Data store version: {data_store_version}")
                
                # Query checkpoint_blobs for the actual data
                cur.execute("""
                    SELECT blob, type
                    FROM checkpoint_blobs
                    WHERE thread_id = %s
                      AND channel = 'data_store'
                      AND version = %s
                    LIMIT 1
                """, (thread_id, data_store_version))
                
                blob_result = cur.fetchone()
                if not blob_result:
                    print(f"No data_store blob found for version: {data_store_version}")
                    return None
                
                blob_data, blob_type = blob_result
                print(f"Blob type: {blob_type}")
                print(f"Blob size: {len(blob_data)} bytes")
                
                # Decode msgpack
                if blob_type == 'msgpack':
                    data_store = msgpack.unpackb(blob_data, raw=False)
                    print("\n=== DATA_STORE CONTENTS ===")
                    print(json.dumps(data_store, indent=2, default=str))
                    return data_store
                else:
                    print(f"Unknown blob type: {blob_type}")
                    return None
                    
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
        return None

def list_recent_threads(limit=10):
    """List recent thread IDs."""
    
    load_env_once(Path(__file__).resolve().parents[1])
    db_uri = os.getenv("DATABASE_URL")
    
    if not db_uri:
        print("ERROR: DATABASE_URL not set")
        return
    
    try:
        with psycopg.connect(db_uri, autocommit=True) as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT DISTINCT
                        thread_id,
                        MAX((checkpoint->>'ts')::timestamp) as latest_ts
                    FROM checkpoints
                    WHERE checkpoint_ns = ''
                    GROUP BY thread_id
                    ORDER BY latest_ts DESC
                    LIMIT %s
                """, (limit,))
                
                print(f"\n=== RECENT {limit} THREADS ===")
                for thread_id, ts in cur.fetchall():
                    print(f"  {thread_id} (last activity: {ts})")
                    
    except Exception as e:
        print(f"ERROR: {e}")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        thread_id = sys.argv[1]
        get_data_store(thread_id)
    else:
        print("Usage: python query_data_store.py <thread_id>")
        print("\nOr run without args to see recent threads:")
        list_recent_threads()
