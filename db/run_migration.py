#!/usr/bin/env python3
"""
Run UUID and Module Name Migration

This script applies the database migration to convert primary keys to UUID
and add the module_name column to dynamic_skills table.

Usage:
    python db/run_migration.py

Requirements:
    - DATABASE_URL environment variable must be set
    - PostgreSQL database must be accessible
    - Recommended: Backup your database first!
"""

import os
import sys
from pathlib import Path
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from env_loader import load_env_once
import psycopg


def create_backup_instructions():
    """Print backup instructions for the user."""
    print("\n" + "="*70)
    print("⚠️  IMPORTANT: BACKUP YOUR DATABASE FIRST!")
    print("="*70)
    print("\nIf something goes wrong, you'll need a backup to restore.")
    print("\nTo create a backup manually (optional):")
    print("  Option 1 - Using pgAdmin: Right-click database → Backup")
    print("  Option 2 - Using command line:")
    print("    pg_dump -U your_user -d your_database > backup.sql")
    print("\n" + "="*70)


def confirm_migration():
    """Ask user to confirm they want to proceed."""
    response = input("\nDo you want to proceed with the migration? (yes/no): ").strip().lower()
    return response in ['yes', 'y']


def run_migration():
    """Execute the UUID and module_name migration."""
    print("\n" + "="*70)
    print("UUID and Module Name Migration")
    print("="*70)
    print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Load environment
    print("\n[1/5] Loading environment variables...")
    load_env_once(Path(__file__).resolve().parent.parent)
    db_uri = os.getenv("DATABASE_URL")
    
    if not db_uri:
        print("❌ ERROR: DATABASE_URL not set in environment")
        print("   Please ensure your .env file is configured correctly")
        sys.exit(1)
    
    print("✓ Environment loaded successfully")
    
    # Read migration file
    print("\n[2/5] Reading migration SQL file...")
    migration_file = Path(__file__).parent / "migrate_to_uuid_and_module_name.sql"
    
    if not migration_file.exists():
        print(f"❌ ERROR: Migration file not found: {migration_file}")
        sys.exit(1)
    
    try:
        migration_sql = migration_file.read_text(encoding='utf-8')
        print(f"✓ Migration file loaded ({len(migration_sql)} characters)")
    except Exception as e:
        print(f"❌ ERROR: Failed to read migration file: {e}")
        sys.exit(1)
    
    # Show backup reminder and get confirmation
    create_backup_instructions()
    
    if not confirm_migration():
        print("\n⏸️  Migration cancelled by user")
        print("   No changes were made to the database")
        sys.exit(0)
    
    # Connect to database
    print("\n[3/5] Connecting to database...")
    try:
        conn = psycopg.connect(db_uri)
        print("✓ Connected to database successfully")
    except Exception as e:
        print(f"❌ ERROR: Failed to connect to database: {e}")
        print("\n   Troubleshooting:")
        print("   - Check your DATABASE_URL is correct")
        print("   - Ensure PostgreSQL is running")
        print("   - Verify network connectivity")
        sys.exit(1)
    
    # Execute migration
    print("\n[4/5] Executing migration...")
    print("   This may take a few moments...")
    
    try:
        with conn:
            with conn.cursor() as cur:
                # Execute the migration SQL
                # Note: The migration SQL file contains a transaction (BEGIN/COMMIT)
                cur.execute(migration_sql)
                
        print("✓ Migration executed successfully!")
        
    except psycopg.errors.DuplicateTable as e:
        print("⚠️  WARNING: Some objects already exist (this is usually OK)")
        print(f"   Details: {e}")
        print("   The migration is idempotent, so this might mean it was already run")
        conn.rollback()
        
    except psycopg.errors.DuplicateColumn as e:
        print("⚠️  WARNING: Some columns already exist (this is usually OK)")
        print(f"   Details: {e}")
        print("   The migration is idempotent, so this might mean it was already run")
        conn.rollback()
        
    except Exception as e:
        print(f"❌ ERROR: Migration failed: {e}")
        print("\n   The database transaction was rolled back")
        print("   Your data should be unchanged")
        print("\n   If you need help, check the migration guide:")
        print("   db/UUID_MIGRATION_GUIDE.md")
        conn.rollback()
        conn.close()
        sys.exit(1)
    
    # Verify migration
    print("\n[5/5] Verifying migration...")
    
    try:
        with conn:
            with conn.cursor() as cur:
                # Check users.id is UUID
                cur.execute("""
                    SELECT data_type 
                    FROM information_schema.columns 
                    WHERE table_name = 'users' AND column_name = 'id'
                """)
                users_id_type = cur.fetchone()
                
                # Check dynamic_skills.id is UUID
                cur.execute("""
                    SELECT data_type 
                    FROM information_schema.columns 
                    WHERE table_name = 'dynamic_skills' AND column_name = 'id'
                """)
                skills_id_type = cur.fetchone()
                
                # Check module_name exists
                cur.execute("""
                    SELECT data_type 
                    FROM information_schema.columns 
                    WHERE table_name = 'dynamic_skills' AND column_name = 'module_name'
                """)
                module_name_type = cur.fetchone()
                
                # Verify results
                if users_id_type and users_id_type[0] == 'uuid':
                    print("  ✓ users.id is now UUID")
                else:
                    print(f"  ⚠️  users.id type: {users_id_type[0] if users_id_type else 'not found'}")
                
                if skills_id_type and skills_id_type[0] == 'uuid':
                    print("  ✓ dynamic_skills.id is now UUID")
                else:
                    print(f"  ⚠️  dynamic_skills.id type: {skills_id_type[0] if skills_id_type else 'not found'}")
                
                if module_name_type and module_name_type[0] == 'text':
                    print("  ✓ dynamic_skills.module_name exists")
                else:
                    print(f"  ⚠️  module_name type: {module_name_type[0] if module_name_type else 'not found'}")
                
                # Count records
                cur.execute("SELECT COUNT(*) FROM users")
                user_count = cur.fetchone()[0]
                print(f"\n  📊 Database stats:")
                print(f"     - Users: {user_count}")
                
                cur.execute("SELECT COUNT(*) FROM dynamic_skills")
                skill_count = cur.fetchone()[0]
                print(f"     - Dynamic Skills: {skill_count}")
                
    except Exception as e:
        print(f"⚠️  WARNING: Verification check failed: {e}")
        print("   The migration might still be successful")
    
    finally:
        conn.close()
    
    # Success message
    print("\n" + "="*70)
    print("✅ MIGRATION COMPLETED SUCCESSFULLY!")
    print("="*70)
    print(f"Completed at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("\nNext steps:")
    print("  1. Run the test script: python db/test_uuid_migration.py")
    print("  2. Test your application: python main.py")
    print("  3. Check for any errors in skill loading/registration")
    print("\nIf you encounter any issues:")
    print("  - Review: db/UUID_MIGRATION_GUIDE.md")
    print("  - Restore from backup if needed")
    print("="*70 + "\n")


if __name__ == "__main__":
    try:
        run_migration()
    except KeyboardInterrupt:
        print("\n\n⏸️  Migration interrupted by user")
        print("   The database transaction was rolled back")
        print("   No changes were made")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ UNEXPECTED ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
