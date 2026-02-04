#!/usr/bin/env python3
"""
Dynamic Skills Migration Script
Migrates dynamic_skills table from source PostgreSQL database to target database.
This script is for one-time use only - delete after migration is complete.

MODIFICATIONS:
- Sets workspace_id to: fc72099f-8957-4cd7-b74e-fe5beecb15f6
- Sets owner_id to: b37928dc-45fc-4342-ad42-e3db6af8f81f
- All other fields are copied from source database

Nelvin Note:
Database level migration is a challenge due to several constraints and cross server configuration issues.
And for a quick solution, we have this script that copies from source and inserts into target.
We customize the workspace id and owner id to the target system, so everything aligns.
Reliable and working script. Until unless further changes are made in DB schema.
"""

import psycopg
from psycopg.types.json import Jsonb
from typing import List, Tuple, Any
import json
from uuid import UUID

# ============================================================
# DATABASE CONFIGURATION - EDIT THESE VALUES
# ============================================================

# Source database (where data is coming FROM)
SOURCE_DB = "postgres://username:password@aiagentic-postgres.cvwog2sooqtl.us-east-2.rds.amazonaws.com:5432/agentic"

# Target database (where data is going TO)
TARGET_DB = "postgres://username:password@aiagentic-framework-prod.cvwog2sooqtl.us-east-2.rds.amazonaws.com:5432/agentic"

# ============================================================
# FIXED VALUES FOR TARGET DATABASE
# ============================================================

# Workspace ID to assign all migrated skills
TARGET_WORKSPACE_ID = "fc72099f-8957-4cd7-b74e-fe5beecb15f6"

# Owner ID to assign all migrated skills
TARGET_OWNER_ID = "b37928dc-45fc-4342-ad42-e3db6af8f81f"

# ============================================================


def migrate_dynamic_skills(
    source_conn,
    target_conn,
    skip_existing: bool = True
) -> Tuple[int, int, int]:
    """
    Migrate dynamic_skills table from source to target database.
    
    Args:
        source_conn: Source database connection
        target_conn: Target database connection
        skip_existing: If True, skip rows that already exist (by id)
    
    Returns:
        Tuple of (total_rows, migrated_rows, skipped_rows)
    """
    print(f"\n{'='*60}")
    print(f"Migrating dynamic_skills table")
    print(f"{'='*60}")
    
    # Define all columns in the latest schema
    source_columns = [
        "id", "name", "module_name", "description", "requires", "produces", 
        "optional_produces", "executor", "hitl_enabled", "prompt", 
        "system_prompt", "llm_model", "rest_config", "action_config", 
        "action_code", "created_at", "updated_at", "created_by", 
        "source", "enabled"
    ]
    
    # Columns that contain JSON/JSONB data
    json_columns = ["requires", "produces", "optional_produces", "rest_config", "action_config"]
    
    # Create a mapping of column names to indices
    col_to_idx = {col: idx for idx, col in enumerate(source_columns)}
    json_col_indices = [col_to_idx[col] for col in json_columns if col in col_to_idx]
    
    # Read data from source
    columns_str = ", ".join(source_columns)
    source_cur = source_conn.cursor()
    source_cur.execute(f"SELECT {columns_str} FROM dynamic_skills ORDER BY created_at")
    rows = source_cur.fetchall()
    total_rows = len(rows)
    
    print(f"[SOURCE] Found {total_rows} rows in dynamic_skills")
    
    if total_rows == 0:
        print(f"[SKIP] No data to migrate")
        return (0, 0, 0)
    
    # Target columns include workspace_id, owner_id, and is_public
    target_columns = source_columns + ["workspace_id", "owner_id", "is_public"]
    target_columns_str = ", ".join(target_columns)
    
    # Prepare insert statement
    placeholders = ", ".join(["%s"] * len(target_columns))
    insert_sql = f"INSERT INTO dynamic_skills ({target_columns_str}) VALUES ({placeholders})"
    
    if skip_existing:
        # Use ON CONFLICT to skip existing rows
        insert_sql += " ON CONFLICT (id) DO NOTHING"
    
    # Insert data into target
    target_cur = target_conn.cursor()
    migrated_count = 0
    skipped_count = 0
    
    print(f"\n[CONFIG] Target workspace_id: {TARGET_WORKSPACE_ID}")
    print(f"[CONFIG] Target owner_id: {TARGET_OWNER_ID}")
    print(f"[CONFIG] is_public: False (default)")
    
    for i, row in enumerate(rows, 1):
        try:
            # Convert row tuple to list so we can modify it
            row_list = list(row)
            
            # Convert dict/list/JSON columns to Jsonb for psycopg3
            for json_idx in json_col_indices:
                if row_list[json_idx] is not None and isinstance(row_list[json_idx], (dict, list)):
                    row_list[json_idx] = Jsonb(row_list[json_idx])
            
            # Add the fixed values for workspace_id, owner_id, and is_public
            row_list.append(TARGET_WORKSPACE_ID)  # workspace_id
            row_list.append(TARGET_OWNER_ID)      # owner_id
            row_list.append(False)                 # is_public
            
            target_cur.execute(insert_sql, tuple(row_list))
            if target_cur.rowcount > 0:
                migrated_count += 1
                # Show first few migrations for verification
                if i <= 3:
                    skill_name = row_list[col_to_idx["name"]]
                    skill_id = row_list[col_to_idx["id"]]
                    print(f"[MIGRATED] '{skill_name}' (ID: {skill_id})")
            else:
                skipped_count += 1
            
            # Progress indicator
            if i % 10 == 0 and i > 3:
                print(f"[PROGRESS] Processed {i}/{total_rows} rows...")
                
        except Exception as e:
            print(f"[ERROR] Failed to insert row {i}: {e}")
            skill_name = row[col_to_idx["name"]] if len(row) > col_to_idx["name"] else "unknown"
            print(f"         Skill name: {skill_name}")
            skipped_count += 1
    
    target_conn.commit()
    
    print(f"\n[TARGET] Migrated {migrated_count} rows")
    print(f"[TARGET] Skipped {skipped_count} rows (already exist or errors)")
    
    return (total_rows, migrated_count, skipped_count)


def verify_migration(source_conn, target_conn) -> bool:
    """Verify that row counts match between source and target."""
    source_cur = source_conn.cursor()
    target_cur = target_conn.cursor()
    
    source_cur.execute("SELECT COUNT(*) FROM dynamic_skills")
    source_count = source_cur.fetchone()[0]
    
    target_cur.execute("SELECT COUNT(*) FROM dynamic_skills")
    target_count = target_cur.fetchone()[0]
    
    print(f"\n[VERIFY] dynamic_skills:")
    print(f"  Source: {source_count} rows")
    print(f"  Target: {target_count} rows")
    
    if source_count == target_count:
        print(f"  ✅ Match!")
        return True
    else:
        print(f"  ⚠️  Mismatch (difference: {source_count - target_count})")
        return False


def verify_target_values(target_conn):
    """Verify that workspace_id and owner_id were set correctly in target."""
    print(f"\n{'='*60}")
    print(f"Verifying Target Values")
    print(f"{'='*60}")
    
    target_cur = target_conn.cursor()
    
    # Check workspace_id
    target_cur.execute("""
        SELECT COUNT(*) 
        FROM dynamic_skills 
        WHERE workspace_id = %s
    """, (TARGET_WORKSPACE_ID,))
    workspace_count = target_cur.fetchone()[0]
    
    # Check owner_id
    target_cur.execute("""
        SELECT COUNT(*) 
        FROM dynamic_skills 
        WHERE owner_id = %s
    """, (TARGET_OWNER_ID,))
    owner_count = target_cur.fetchone()[0]
    
    # Check is_public
    target_cur.execute("""
        SELECT COUNT(*) 
        FROM dynamic_skills 
        WHERE is_public = FALSE
    """, )
    public_count = target_cur.fetchone()[0]
    
    # Get total count
    target_cur.execute("SELECT COUNT(*) FROM dynamic_skills")
    total_count = target_cur.fetchone()[0]
    
    print(f"\n[CHECK] Skills with workspace_id '{TARGET_WORKSPACE_ID}': {workspace_count}/{total_count}")
    print(f"[CHECK] Skills with owner_id '{TARGET_OWNER_ID}': {owner_count}/{total_count}")
    print(f"[CHECK] Skills with is_public = FALSE: {public_count}/{total_count}")
    
    # Sample check - show a few migrated skills
    target_cur.execute("""
        SELECT name, id, workspace_id, owner_id, is_public, executor
        FROM dynamic_skills
        ORDER BY created_at
        LIMIT 5
    """)
    
    print(f"\n[SAMPLE] First 5 skills in target database:")
    print(f"{'-'*60}")
    for row in target_cur.fetchall():
        name, skill_id, ws_id, own_id, is_pub, executor = row
        print(f"  • {name}")
        print(f"    ID: {skill_id}")
        print(f"    Workspace: {ws_id}")
        print(f"    Owner: {own_id}")
        print(f"    Public: {is_pub}, Executor: {executor}")


def main():
    """Main migration process."""
    print("\n" + "="*60)
    print("Dynamic Skills Migration Script")
    print("="*60)
    
    # Validate configuration
    if "username:password" in SOURCE_DB or "username:password" in TARGET_DB:
        print("\n[ERROR] Please edit the SOURCE_DB and TARGET_DB connection strings")
        print("        Replace 'username:password@localhost:5432/database_name' with actual values")
        return
    
    print(f"\nSource: {SOURCE_DB.split('@')[1] if '@' in SOURCE_DB else 'N/A'}")
    print(f"Target: {TARGET_DB.split('@')[1] if '@' in TARGET_DB else 'N/A'}")
    
    # Validate UUID format
    try:
        UUID(TARGET_WORKSPACE_ID)
        UUID(TARGET_OWNER_ID)
    except ValueError as e:
        print(f"\n[ERROR] Invalid UUID format: {e}")
        return
    
    # Confirm before proceeding
    print("\n⚠️  WARNING: This will copy dynamic_skills data from source to target database.")
    print("   Fixed values will be used for:")
    print(f"     - workspace_id: {TARGET_WORKSPACE_ID}")
    print(f"     - owner_id: {TARGET_OWNER_ID}")
    print(f"     - is_public: False")
    print("   Existing rows with matching IDs will be skipped (ON CONFLICT DO NOTHING)")
    response = input("\nProceed with migration? (yes/no): ")
    
    if response.lower() not in ['yes', 'y']:
        print("\n[CANCELLED] Migration cancelled by user")
        return
    
    try:
        # Connect to databases
        print("\n[CONNECT] Connecting to source database...")
        source_conn = psycopg.connect(SOURCE_DB)
        print("[CONNECT] Connected to source ✅")
        
        print("[CONNECT] Connecting to target database...")
        target_conn = psycopg.connect(TARGET_DB)
        print("[CONNECT] Connected to target ✅")
        
        # Perform migration
        total, migrated, skipped = migrate_dynamic_skills(
            source_conn, 
            target_conn, 
            skip_existing=True
        )
        
        # Verify migration
        print("\n" + "="*60)
        print("Verification")
        print("="*60)
        
        verified = verify_migration(source_conn, target_conn)
        
        # Verify target-specific values
        verify_target_values(target_conn)
        
        # Summary
        print("\n" + "="*60)
        print("Migration Summary")
        print("="*60)
        
        print(f"\ndynamic_skills:")
        print(f"  Total rows in source: {total}")
        print(f"  Rows migrated: {migrated}")
        print(f"  Rows skipped: {skipped}")
        
        if verified:
            print("\n✅ Migration verified successfully!")
        else:
            print("\n⚠️  Row count mismatch - please review")
        
        # Close connections
        source_conn.close()
        target_conn.close()
        
        print("\n" + "="*60)
        print("Migration Complete!")
        print("="*60)
        print("\n💡 TIP: Delete this script after successful migration\n")
        
    except psycopg.OperationalError as e:
        print(f"\n[ERROR] Database connection failed: {e}")
        print("\nPlease check your connection strings:")
        print("  - Hostname and port are correct")
        print("  - Database name exists")
        print("  - Username and password are correct")
        print("  - Database is accessible from this machine")
        
    except Exception as e:
        print(f"\n[ERROR] Migration failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
