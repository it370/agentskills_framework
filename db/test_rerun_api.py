#!/usr/bin/env python3
"""
Integration test for the rerun API endpoint.
"""
import sys
import json
import asyncio
import httpx
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from env_loader import load_env_once

async def test_rerun_api():
    """Test the rerun API endpoint."""
    print("\n" + "="*60)
    print("Testing Rerun API Endpoint")
    print("="*60)
    
    # Load environment
    load_env_once(Path(__file__).resolve().parent.parent)
    
    api_base = "http://localhost:8000"
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            # Test 1: Create a test run
            print("\n[Test 1] Starting a test workflow...")
            test_thread_id = f"thread_api_test_{int(asyncio.get_event_loop().time())}"
            
            start_payload = {
                "thread_id": test_thread_id,
                "sop": "Test SOP for rerun functionality",
                "initial_data": {"test_key": "test_value", "order_id": "12345"}
            }
            
            response = await client.post(f"{api_base}/start", json=start_payload)
            print(f"  Status: {response.status_code}")
            
            if response.status_code == 200:
                result = response.json()
                print(f"  ✓ Started: {result.get('thread_id')}")
            else:
                print(f"  ✗ Failed to start: {response.text}")
                return False
            
            # Wait a moment for metadata to be saved
            await asyncio.sleep(2)
            
            # Test 2: Get run metadata
            print("\n[Test 2] Getting run metadata...")
            response = await client.get(f"{api_base}/admin/runs/{test_thread_id}/metadata")
            print(f"  Status: {response.status_code}")
            
            if response.status_code == 200:
                metadata = response.json()
                print(f"  ✓ Got metadata:")
                print(f"    Thread ID: {metadata.get('thread_id')}")
                print(f"    SOP: {metadata.get('sop')[:50]}...")
                print(f"    Initial Data: {metadata.get('initial_data')}")
                print(f"    Rerun Count: {metadata.get('rerun_count')}")
            else:
                print(f"  ✗ Failed to get metadata: {response.text}")
                return False
            
            # Test 3: Rerun the workflow
            print("\n[Test 3] Rerunning the workflow...")
            response = await client.post(f"{api_base}/rerun/{test_thread_id}")
            print(f"  Status: {response.status_code}")
            
            if response.status_code == 200:
                rerun_result = response.json()
                print(f"  ✓ Rerun started:")
                print(f"    New Thread ID: {rerun_result.get('thread_id')}")
                print(f"    Parent Thread ID: {rerun_result.get('parent_thread_id')}")
                print(f"    Rerun Count: {rerun_result.get('rerun_count')}")
                
                new_thread_id = rerun_result.get('thread_id')
            else:
                print(f"  ✗ Failed to rerun: {response.text}")
                return False
            
            # Wait a moment for the new run metadata to be saved
            await asyncio.sleep(2)
            
            # Test 4: Verify new run metadata
            print("\n[Test 4] Verifying new run metadata...")
            response = await client.get(f"{api_base}/admin/runs/{new_thread_id}/metadata")
            print(f"  Status: {response.status_code}")
            
            if response.status_code == 200:
                new_metadata = response.json()
                print(f"  ✓ Got new run metadata:")
                print(f"    Thread ID: {new_metadata.get('thread_id')}")
                print(f"    Parent Thread ID: {new_metadata.get('parent_thread_id')}")
                print(f"    Rerun Count: {new_metadata.get('rerun_count')}")
                print(f"    Same SOP: {new_metadata.get('sop') == metadata.get('sop')}")
                print(f"    Same Initial Data: {new_metadata.get('initial_data') == metadata.get('initial_data')}")
            else:
                print(f"  ✗ Failed to get new metadata: {response.text}")
                return False
            
            # Test 5: List all runs
            print("\n[Test 5] Listing runs to verify both appear...")
            response = await client.get(f"{api_base}/admin/runs?limit=100")
            print(f"  Status: {response.status_code}")
            
            if response.status_code == 200:
                runs_data = response.json()
                runs = runs_data.get('runs', [])
                print(f"  ✓ Found {len(runs)} total run(s)")
                
                # Find our test runs
                test_runs = [r for r in runs if r.get('thread_id') in [test_thread_id, new_thread_id]]
                print(f"  ✓ Found {len(test_runs)} test run(s):")
                for run in test_runs:
                    print(f"    - {run.get('thread_id')} (status: {run.get('status', 'unknown')})")
            else:
                print(f"  ✗ Failed to list runs: {response.text}")
            
            print("\n" + "="*60)
            print("✓ All API tests passed!")
            print("="*60)
            return True
            
        except Exception as e:
            print(f"\n✗ ERROR: {e}")
            import traceback
            traceback.print_exc()
            return False

if __name__ == "__main__":
    success = asyncio.run(test_rerun_api())
    sys.exit(0 if success else 1)
