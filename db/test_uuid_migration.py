#!/usr/bin/env python3
"""
Test script to verify UUID migration and module_name functionality.

This script tests:
1. UUID primary keys in users and dynamic_skills tables
2. Module name auto-generation from skill names
3. Skill registration with module_name
4. Foreign key relationships with UUID
"""

import os
import sys
from pathlib import Path
import uuid

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from env_loader import load_env_once
import psycopg


def test_uuid_format(value):
    """Test if value is a valid UUID."""
    try:
        uuid.UUID(str(value))
        return True
    except (ValueError, AttributeError):
        return False


def run_tests():
    """Run all migration tests."""
    print("\n" + "="*60)
    print("UUID and Module Name Migration Tests")
    print("="*60)
    
    # Load environment
    load_env_once(Path(__file__).resolve().parent.parent)
    db_uri = os.getenv("DATABASE_URL")
    
    if not db_uri:
        print("\n[ERROR] DATABASE_URL not set")
        sys.exit(1)
    
    tests_passed = 0
    tests_failed = 0
    
    try:
        with psycopg.connect(db_uri) as conn:
            with conn.cursor() as cur:
                
                # Test 1: Check users table uses UUID
                print("\n[TEST 1] Checking users.id is UUID...")
                cur.execute("""
                    SELECT column_name, data_type 
                    FROM information_schema.columns 
                    WHERE table_name = 'users' AND column_name = 'id'
                """)
                result = cur.fetchone()
                if result and result[1] == 'uuid':
                    print("✓ users.id is UUID type")
                    tests_passed += 1
                else:
                    print(f"✗ users.id is not UUID (found: {result[1] if result else 'not found'})")
                    tests_failed += 1
                
                # Test 2: Check dynamic_skills table uses UUID
                print("\n[TEST 2] Checking dynamic_skills.id is UUID...")
                cur.execute("""
                    SELECT column_name, data_type 
                    FROM information_schema.columns 
                    WHERE table_name = 'dynamic_skills' AND column_name = 'id'
                """)
                result = cur.fetchone()
                if result and result[1] == 'uuid':
                    print("✓ dynamic_skills.id is UUID type")
                    tests_passed += 1
                else:
                    print(f"✗ dynamic_skills.id is not UUID (found: {result[1] if result else 'not found'})")
                    tests_failed += 1
                
                # Test 3: Check module_name column exists
                print("\n[TEST 3] Checking module_name column exists...")
                cur.execute("""
                    SELECT column_name, data_type, is_nullable
                    FROM information_schema.columns 
                    WHERE table_name = 'dynamic_skills' AND column_name = 'module_name'
                """)
                result = cur.fetchone()
                if result and result[1] == 'text' and result[2] == 'NO':
                    print("✓ module_name column exists (TEXT NOT NULL)")
                    tests_passed += 1
                else:
                    print(f"✗ module_name column issue (found: {result})")
                    tests_failed += 1
                
                # Test 4: Check module_name has unique constraint
                print("\n[TEST 4] Checking module_name unique constraint...")
                cur.execute("""
                    SELECT constraint_name 
                    FROM information_schema.table_constraints 
                    WHERE table_name = 'dynamic_skills' 
                    AND constraint_type = 'UNIQUE'
                    AND constraint_name LIKE '%module_name%'
                """)
                result = cur.fetchone()
                if result:
                    print(f"✓ module_name has unique constraint: {result[0]}")
                    tests_passed += 1
                else:
                    print("✗ module_name unique constraint not found")
                    tests_failed += 1
                
                # Test 5: Test module_name generation function
                print("\n[TEST 5] Testing module_name generation function...")
                test_cases = [
                    ("Data Processing", "data_processing"),
                    ("Criminal-Verifier", "criminal_verifier"),
                    ("Agent Education 2024", "agent_education_2024"),
                    ("REST API Validator!", "rest_api_validator"),
                    ("Test___Skill", "test_skill"),
                    ("_Leading_Trailing_", "leading_trailing"),
                ]
                
                all_passed = True
                for input_name, expected_output in test_cases:
                    cur.execute("SELECT generate_module_name(%s)", (input_name,))
                    result = cur.fetchone()[0]
                    if result == expected_output:
                        print(f"  ✓ '{input_name}' → '{result}'")
                    else:
                        print(f"  ✗ '{input_name}' → '{result}' (expected '{expected_output}')")
                        all_passed = False
                
                if all_passed:
                    print("✓ All module_name generation tests passed")
                    tests_passed += 1
                else:
                    print("✗ Some module_name generation tests failed")
                    tests_failed += 1
                
                # Test 6: Test auto-generation trigger
                print("\n[TEST 6] Testing module_name auto-generation trigger...")
                test_skill_name = f"Test Skill {uuid.uuid4().hex[:8]}"
                try:
                    cur.execute("""
                        INSERT INTO dynamic_skills (name, description)
                        VALUES (%s, 'Test description')
                        RETURNING id, name, module_name
                    """, (test_skill_name,))
                    skill_id, name, module_name = cur.fetchone()
                    
                    if test_uuid_format(skill_id):
                        print(f"  ✓ ID is valid UUID: {skill_id}")
                    else:
                        print(f"  ✗ ID is not valid UUID: {skill_id}")
                        all_passed = False
                    
                    expected_module_name = test_skill_name.lower().replace(' ', '_')
                    if module_name == expected_module_name:
                        print(f"  ✓ module_name auto-generated: '{module_name}'")
                    else:
                        print(f"  ✗ module_name mismatch: '{module_name}' (expected '{expected_module_name}')")
                        all_passed = False
                    
                    # Clean up test skill
                    cur.execute("DELETE FROM dynamic_skills WHERE id = %s", (skill_id,))
                    conn.commit()
                    
                    if all_passed:
                        print("✓ Auto-generation trigger works correctly")
                        tests_passed += 1
                    else:
                        print("✗ Auto-generation trigger has issues")
                        tests_failed += 1
                except Exception as e:
                    print(f"✗ Trigger test failed: {e}")
                    tests_failed += 1
                    conn.rollback()
                
                # Test 7: Check foreign key updates for users
                print("\n[TEST 7] Checking foreign key updates (user_id)...")
                fk_tables = []
                
                # Check password_reset_tokens
                cur.execute("""
                    SELECT column_name, data_type 
                    FROM information_schema.columns 
                    WHERE table_name = 'password_reset_tokens' AND column_name = 'user_id'
                """)
                result = cur.fetchone()
                if result and result[1] == 'uuid':
                    fk_tables.append('password_reset_tokens')
                
                # Check user_sessions
                cur.execute("""
                    SELECT column_name, data_type 
                    FROM information_schema.columns 
                    WHERE table_name = 'user_sessions' AND column_name = 'user_id'
                """)
                result = cur.fetchone()
                if result and result[1] == 'uuid':
                    fk_tables.append('user_sessions')
                
                # Check run_metadata (if exists)
                cur.execute("""
                    SELECT column_name, data_type 
                    FROM information_schema.columns 
                    WHERE table_name = 'run_metadata' AND column_name = 'user_id'
                """)
                result = cur.fetchone()
                if result and result[1] == 'uuid':
                    fk_tables.append('run_metadata')
                
                if fk_tables:
                    print(f"✓ Foreign key columns updated to UUID: {', '.join(fk_tables)}")
                    tests_passed += 1
                else:
                    print("✗ No foreign key columns found or not updated to UUID")
                    tests_failed += 1
                
                # Test 8: Verify existing data (if any)
                print("\n[TEST 8] Checking existing data integrity...")
                
                # Check users
                cur.execute("SELECT COUNT(*), COUNT(DISTINCT id) FROM users")
                user_count, unique_ids = cur.fetchone()
                if user_count == unique_ids:
                    print(f"  ✓ Users table: {user_count} records, all IDs unique")
                else:
                    print(f"  ✗ Users table: ID uniqueness issue")
                
                # Check dynamic_skills
                cur.execute("SELECT COUNT(*), COUNT(DISTINCT id), COUNT(DISTINCT module_name) FROM dynamic_skills")
                skill_count, unique_ids, unique_modules = cur.fetchone()
                if skill_count == unique_ids == unique_modules:
                    print(f"  ✓ Dynamic skills table: {skill_count} records, all IDs and module_names unique")
                    tests_passed += 1
                else:
                    print(f"  ✗ Dynamic skills table: uniqueness issue (count={skill_count}, unique_ids={unique_ids}, unique_modules={unique_modules})")
                    tests_failed += 1
                
    except Exception as e:
        print(f"\n[ERROR] Test execution failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    
    # Summary
    print("\n" + "="*60)
    print("Test Summary")
    print("="*60)
    print(f"Tests Passed: {tests_passed}")
    print(f"Tests Failed: {tests_failed}")
    print(f"Total Tests:  {tests_passed + tests_failed}")
    
    if tests_failed == 0:
        print("\n✓ All tests passed! Migration is successful.")
        print("="*60 + "\n")
        sys.exit(0)
    else:
        print(f"\n✗ {tests_failed} test(s) failed. Please review the migration.")
        print("="*60 + "\n")
        sys.exit(1)


if __name__ == "__main__":
    run_tests()
