#!/usr/bin/env python3
"""
Test script to verify run metadata and rerun functionality.
"""
import sys
import json
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from env_loader import load_env_once
import psycopg
import os

def test_run_metadata():
    """Test the run_metadata table and rerun functionality."""
    print("\n" + "="*60)
    print("Testing Run Metadata & Rerun Functionality")
    print("="*60)
    
    # Load environment
    load_env_once(Path(__file__).resolve().parent.parent)
    
    db_uri = os.getenv("DATABASE_URL")
    if not db_uri:
        print("\n✗ ERROR: DATABASE_URL not set in environment")
        return False
    
    try:
        with psycopg.connect(db_uri, autocommit=True) as conn:
            with conn.cursor() as cur:
                # Test 1: Insert test run metadata
                print("\n[Test 1] Inserting test run metadata...")
                test_thread_id = "test_thread_rerun_001"
                test_sop = "Test workflow for rerun functionality"
                test_data = {"order_number": "TEST001", "test_mode": True}
                
                cur.execute("""
                    INSERT INTO run_metadata (thread_id, sop, initial_data)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (thread_id) DO UPDATE
                    SET sop = EXCLUDED.sop,
                        initial_data = EXCLUDED.initial_data
                    RETURNING thread_id, created_at
                """, (test_thread_id, test_sop, json.dumps(test_data)))
                
                result = cur.fetchone()
                print(f"✓ Inserted/Updated: {result[0]} at {result[1]}")
                
                # Test 2: Query the inserted data
                print("\n[Test 2] Querying run metadata...")
                cur.execute("""
                    SELECT thread_id, sop, initial_data, created_at, rerun_count
                    FROM run_metadata
                    WHERE thread_id = %s
                """, (test_thread_id,))
                
                row = cur.fetchone()
                if row:
                    print(f"✓ Found metadata:")
                    print(f"  Thread ID: {row[0]}")
                    print(f"  SOP: {row[1]}")
                    print(f"  Initial Data: {row[2]}")
                    print(f"  Created At: {row[3]}")
                    print(f"  Rerun Count: {row[4]}")
                else:
                    print("✗ No metadata found")
                    return False
                
                # Test 3: Simulate a rerun
                print("\n[Test 3] Simulating rerun...")
                rerun_thread_id = f"{test_thread_id}_rerun_1"
                
                cur.execute("""
                    INSERT INTO run_metadata (thread_id, sop, initial_data, parent_thread_id, rerun_count)
                    VALUES (%s, %s, %s, %s, %s)
                    RETURNING thread_id, parent_thread_id, rerun_count
                """, (rerun_thread_id, test_sop, json.dumps(test_data), test_thread_id, 1))
                
                rerun_result = cur.fetchone()
                print(f"✓ Created rerun: {rerun_result[0]}")
                print(f"  Parent: {rerun_result[1]}")
                print(f"  Rerun Count: {rerun_result[2]}")
                
                # Test 4: Query all runs including reruns
                print("\n[Test 4] Querying all test runs...")
                cur.execute("""
                    SELECT thread_id, parent_thread_id, rerun_count
                    FROM run_metadata
                    WHERE thread_id LIKE %s
                    ORDER BY created_at
                """, (f"{test_thread_id}%",))
                
                rows = cur.fetchall()
                print(f"✓ Found {len(rows)} test run(s):")
                for row in rows:
                    parent_info = f" (parent: {row[1]})" if row[1] else " (original)"
                    print(f"  - {row[0]}{parent_info} - Rerun count: {row[2]}")
                
                # Test 5: Verify indexes
                print("\n[Test 5] Verifying indexes...")
                cur.execute("""
                    SELECT indexname 
                    FROM pg_indexes 
                    WHERE tablename = 'run_metadata'
                """)
                indexes = [row[0] for row in cur.fetchall()]
                print(f"✓ Found {len(indexes)} index(es):")
                for idx in indexes:
                    print(f"  - {idx}")
                
                print("\n" + "="*60)
                print("✓ All tests passed!")
                print("="*60)
                return True
                
    except Exception as e:
        print(f"\n✗ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_run_metadata()
    sys.exit(0 if success else 1)
