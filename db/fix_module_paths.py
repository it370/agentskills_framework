#!/usr/bin/env python3
"""
Fix module paths in existing skills.

This script updates the action_config.module field in dynamic_skills
to use the correct module_name instead of the raw skill name.

Usage:
    python db/fix_module_paths.py
"""

import os
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from env_loader import load_env_once
import psycopg


def fix_module_paths():
    """Fix module paths for all python_function action skills."""
    print("\n" + "="*70)
    print("Fix Module Paths in Dynamic Skills")
    print("="*70)
    
    # Load environment
    load_env_once(Path(__file__).resolve().parent.parent)
    db_uri = os.getenv("DATABASE_URL")
    
    if not db_uri:
        print("❌ ERROR: DATABASE_URL not set in environment")
        sys.exit(1)
    
    try:
        with psycopg.connect(db_uri) as conn:
            with conn.cursor() as cur:
                # Check current state
                print("\n[1/3] Checking current skills...")
                cur.execute("""
                    SELECT 
                        name,
                        module_name,
                        action_config->>'module' as current_module,
                        action_config->>'function' as function_name
                    FROM dynamic_skills
                    WHERE executor = 'action'
                      AND action_config->>'type' = 'python_function'
                    ORDER BY name
                """)
                
                skills = cur.fetchall()
                
                if not skills:
                    print("  ℹ️  No python_function skills found")
                    return
                
                print(f"  Found {len(skills)} python_function skills:")
                needs_fix = []
                for name, module_name, current_module, function_name in skills:
                    expected_module = f"dynamic_skills.{module_name}"
                    status = "✓" if current_module == expected_module else "✗"
                    print(f"    {status} {name}")
                    print(f"       Module: {current_module or '(not set)'}")
                    print(f"       Expected: {expected_module}")
                    if current_module != expected_module:
                        needs_fix.append((name, module_name, current_module, expected_module))
                
                if not needs_fix:
                    print("\n✓ All skills already have correct module paths!")
                    return
                
                # Fix the skills
                print(f"\n[2/3] Fixing {len(needs_fix)} skills...")
                cur.execute("""
                    UPDATE dynamic_skills
                    SET action_config = jsonb_set(
                        action_config,
                        '{module}',
                        to_jsonb('dynamic_skills.' || module_name)
                    )
                    WHERE executor = 'action'
                      AND action_config->>'type' = 'python_function'
                      AND (
                          action_config->>'module' != 'dynamic_skills.' || module_name
                          OR action_config->>'module' IS NULL
                      )
                """)
                
                updated_count = cur.rowcount
                conn.commit()
                print(f"  ✓ Updated {updated_count} skills")
                
                # Verify
                print("\n[3/3] Verifying fixes...")
                cur.execute("""
                    SELECT 
                        name,
                        module_name,
                        action_config->>'module' as current_module
                    FROM dynamic_skills
                    WHERE executor = 'action'
                      AND action_config->>'type' = 'python_function'
                    ORDER BY name
                """)
                
                all_correct = True
                for name, module_name, current_module in cur.fetchall():
                    expected_module = f"dynamic_skills.{module_name}"
                    if current_module == expected_module:
                        print(f"  ✓ {name}: {current_module}")
                    else:
                        print(f"  ✗ {name}: {current_module} (expected: {expected_module})")
                        all_correct = False
                
                print("\n" + "="*70)
                if all_correct:
                    print("✅ All module paths fixed successfully!")
                else:
                    print("⚠️  Some skills still have incorrect module paths")
                print("="*70 + "\n")
                
                print("Next steps:")
                print("  1. Restart your application: python main.py")
                print("  2. Test the skills to ensure they work correctly")
                print("  3. Check logs for any 'Cannot import module' errors")
                
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    try:
        fix_module_paths()
    except KeyboardInterrupt:
        print("\n\n⏸️  Operation cancelled by user")
        sys.exit(1)
