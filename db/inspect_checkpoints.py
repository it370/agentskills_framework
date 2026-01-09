#!/usr/bin/env python3
"""
Inspect checkpoint tables and find how to query data_store.
Nelvin Note: For Dev Usage only
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from env_loader import load_env_once
import psycopg
import json

def inspect_checkpoints():
    """Inspect checkpoint table structure and show how to query data_store."""
    
    load_env_once(Path(__file__).resolve().parents[1])
    db_uri = os.getenv("DATABASE_URL")
    
    if not db_uri:
        print("ERROR: DATABASE_URL not set")
        return 1
    
    try:
        with psycopg.connect(db_uri, autocommit=True) as conn:
            with conn.cursor() as cur:
                # 1. List all checkpoint-related tables
                print("=== CHECKPOINT TABLES ===")
                cur.execute("""
                    SELECT table_name 
                    FROM information_schema.tables 
                    WHERE table_schema = 'public' 
                      AND table_name LIKE 'checkpoint%'
                    ORDER BY table_name
                """)
                tables = cur.fetchall()
                for table in tables:
                    print(f"  - {table[0]}")
                
                # 2. Show checkpoint_writes structure if it exists
                print("\n=== CHECKPOINT_WRITES COLUMNS ===")
                cur.execute("""
                    SELECT column_name, data_type 
                    FROM information_schema.columns 
                    WHERE table_name = 'checkpoint_writes'
                    ORDER BY ordinal_position
                """)
                columns = cur.fetchall()
                if columns:
                    for col, dtype in columns:
                        print(f"  {col}: {dtype}")
                else:
                    print("  (table does not exist)")
                
                # 3. Get a sample row from checkpoint_writes
                if columns:
                    print("\n=== SAMPLE CHECKPOINT_WRITES ROW ===")
                    cur.execute("SELECT * FROM checkpoint_writes LIMIT 1")
                    row = cur.fetchone()
                    if row:
                        col_names = [desc[0] for desc in cur.description]
                        for i, col_name in enumerate(col_names):
                            val = row[i]
                            if isinstance(val, dict):
                                print(f"  {col_name}: {json.dumps(val, indent=2, default=str)[:200]}...")
                            else:
                                print(f"  {col_name}: {str(val)[:100]}")
                
                # 4. Get a sample checkpoint with channel_versions
                print("\n=== SAMPLE CHECKPOINT STRUCTURE ===")
                cur.execute("""
                    SELECT 
                        thread_id,
                        checkpoint_id,
                        checkpoint->'channel_versions' as channel_versions
                    FROM checkpoints
                    WHERE checkpoint_ns = ''
                    ORDER BY (checkpoint->>'ts')::timestamp DESC
                    LIMIT 1
                """)
                row = cur.fetchone()
                if row:
                    thread_id, checkpoint_id, versions = row
                    print(f"  Thread: {thread_id}")
                    print(f"  Checkpoint ID: {checkpoint_id}")
                    print(f"  Channel Versions: {json.dumps(versions, indent=2, default=str)[:500]}")
                
                # 5. Try to find the actual data_store
                print("\n=== FINDING ACTUAL DATA_STORE ===")
                
                # Get the data_store reference from latest checkpoint
                cur.execute("""
                    SELECT 
                        thread_id,
                        checkpoint_id,
                        checkpoint->'channel_versions'->>'data_store' as data_store_ref
                    FROM checkpoints
                    WHERE checkpoint_ns = ''
                    ORDER BY (checkpoint->>'ts')::timestamp DESC
                    LIMIT 1
                """)
                row = cur.fetchone()
                
                if row:
                    thread_id, cp_id, data_store_ref = row
                    print(f"  Thread: {thread_id}")
                    print(f"  Data store ref: {data_store_ref}")
                    
                    if data_store_ref:
                        # Parse the reference: {checkpoint_id}.{task_id}.{hash}
                        parts = data_store_ref.split('.')
                        ref_checkpoint_id = parts[0]
                        ref_task_id = parts[1] if len(parts) > 1 else '0'
                        
                        print(f"  Parsed - Checkpoint: {ref_checkpoint_id}, Task: {ref_task_id}")
                        
                        # Query using blob column and decode msgpack
                        try:
                            import msgpack
                            
                            # First try with the parsed task_id
                            query = """
                                SELECT channel, blob, type, task_id
                                FROM checkpoint_writes
                                WHERE checkpoint_id = %s
                                  AND channel = 'data_store'
                                ORDER BY idx DESC
                                LIMIT 5
                            """
                            cur.execute(query, (ref_checkpoint_id,))
                            results = cur.fetchall()
                            
                            if results:
                                print(f"\n  Found {len(results)} data_store writes for checkpoint {ref_checkpoint_id}")
                                for channel, blob_data, data_type, task_id in results:
                                    print(f"\n  Task ID: {task_id}")
                                    print(f"  Type: {data_type}")
                                    
                                    # Decode msgpack
                                    if data_type == 'msgpack' and blob_data:
                                        try:
                                            decoded = msgpack.unpackb(blob_data, raw=False)
                                            print(f"  Decoded data_store content:")
                                            print(json.dumps(decoded, indent=2, default=str)[:500])
                                        except Exception as e:
                                            print(f"  Error decoding: {e}")
                                    else:
                                        print(f"  Raw blob (first 100 bytes): {str(blob_data[:100])}")
                            else:
                                print(f"\n  No data_store found in checkpoint_writes for checkpoint {ref_checkpoint_id}")
                                
                                # Try checkpoint_blobs table
                                print("\n  Trying checkpoint_blobs table...")
                                
                                # First check structure
                                cur.execute("""
                                    SELECT column_name 
                                    FROM information_schema.columns 
                                    WHERE table_name = 'checkpoint_blobs'
                                    ORDER BY ordinal_position
                                """)
                                blob_cols = [row[0] for row in cur.fetchall()]
                                print(f"  checkpoint_blobs columns: {blob_cols}")
                                
                                # Query with correct columns
                                cur.execute("""
                                    SELECT * FROM checkpoint_blobs LIMIT 1
                                """)
                                sample_blob = cur.fetchone()
                                if sample_blob:
                                    col_names = [desc[0] for desc in cur.description]
                                    print(f"  Sample row:")
                                    for i, col in enumerate(col_names):
                                        val = sample_blob[i]
                                        if isinstance(val, bytes):
                                            print(f"    {col}: <binary data, {len(val)} bytes>")
                                        else:
                                            print(f"    {col}: {str(val)[:100]}")
                                
                                # Generate the working query
                                print("\n=== WORKING QUERY TO GET DATA_STORE ===")
                                working_query = f"""
-- Get the latest data_store for a specific thread (PostgreSQL + Python)
-- Note: Data is stored as msgpack binary, must decode in application

WITH latest_checkpoint AS (
    SELECT 
        checkpoint_id,
        checkpoint->'channel_versions'->>'data_store' as data_store_ref
    FROM checkpoints
    WHERE thread_id = 'YOUR_THREAD_ID_HERE'
      AND checkpoint_ns = ''
    ORDER BY (checkpoint->>'ts')::timestamp DESC
    LIMIT 1
)
SELECT 
    w.channel,
    w.blob,  -- This is msgpack-encoded binary
    w.type   -- Should be 'msgpack'
FROM latest_checkpoint lc
CROSS JOIN LATERAL (
    SELECT split_part(lc.data_store_ref, '.', 1) as cp_id,
           split_part(lc.data_store_ref, '.', 2) as task_id
) refs
JOIN checkpoint_writes w ON w.checkpoint_id = refs.cp_id 
                         AND w.task_id = refs.task_id
                         AND w.channel = 'data_store';

-- In Python, decode with:
-- import msgpack
-- data_store = msgpack.unpackb(blob, raw=False)
"""
                                print(working_query)
                        except ImportError:
                            print("\n  ERROR: msgpack library not installed")
                            print("  Install with: pip install msgpack")
                        except Exception as e:
                            print(f"\n  ERROR decoding msgpack: {e}")
                            import traceback
                            traceback.print_exc()
    
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(inspect_checkpoints())
