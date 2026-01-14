#!/usr/bin/env python3
"""
TEMPORARY DATA MIGRATION SCRIPT
Migrates dynamic_skills and run_metadata tables from one PostgreSQL database to another.
This script is for one-time use only - delete after migration is complete.
"""

import psycopg
from psycopg.types.json import Jsonb
from typing import List, Tuple, Any
import json

# ============================================================
# DATABASE CONFIGURATION - EDIT THESE VALUES
# ============================================================

# Source database (where data is coming FROM)
SOURCE_DB = "postgres://avnadmin:password@pg-3676625a-robocop-fcf4.i.aivencloud.com:10200/defaultdb?sslmode=require"

# Target database (where data is going TO)
TARGET_DB = "postgres://postgres:password@aiagentic-postgres.cvwog2sooqtl.us-east-2.rds.amazonaws.com:5432/agentic"

# ============================================================


def migrate_table(
    source_conn,
    target_conn,
    table_name: str,
    columns: List[str],
    json_columns: List[str] = None,
    skip_existing: bool = True
) -> Tuple[int, int, int]:
    """
    Migrate a table from source to target database.
    
    Args:
        source_conn: Source database connection
        target_conn: Target database connection
        table_name: Name of the table to migrate
        columns: List of column names
        json_columns: List of column names that contain JSON/JSONB data
        skip_existing: If True, skip rows that already exist (by primary key)
    
    Returns:
        Tuple of (total_rows, migrated_rows, skipped_rows)
    """
    print(f"\n{'='*60}")
    print(f"Migrating table: {table_name}")
    print(f"{'='*60}")
    
    if json_columns is None:
        json_columns = []
    
    # Create a mapping of column names to indices
    col_to_idx = {col: idx for idx, col in enumerate(columns)}
    json_col_indices = [col_to_idx[col] for col in json_columns if col in col_to_idx]
    
    # Read data from source
    columns_str = ", ".join(columns)
    source_cur = source_conn.cursor()
    source_cur.execute(f"SELECT {columns_str} FROM {table_name} ORDER BY id")
    rows = source_cur.fetchall()
    total_rows = len(rows)
    
    print(f"[SOURCE] Found {total_rows} rows in {table_name}")
    
    if total_rows == 0:
        print(f"[SKIP] No data to migrate")
        return (0, 0, 0)
    
    # Prepare insert statement
    placeholders = ", ".join(["%s"] * len(columns))
    insert_sql = f"INSERT INTO {table_name} ({columns_str}) VALUES ({placeholders})"
    
    if skip_existing:
        # Use ON CONFLICT to skip existing rows
        insert_sql += " ON CONFLICT (id) DO NOTHING"
    
    # Insert data into target
    target_cur = target_conn.cursor()
    migrated_count = 0
    skipped_count = 0
    
    for i, row in enumerate(rows, 1):
        try:
            # Convert row tuple to list so we can modify it
            row_list = list(row)
            
            # Convert dict/list/JSON columns to Jsonb for psycopg3
            for json_idx in json_col_indices:
                if row_list[json_idx] is not None and isinstance(row_list[json_idx], (dict, list)):
                    row_list[json_idx] = Jsonb(row_list[json_idx])
            
            target_cur.execute(insert_sql, tuple(row_list))
            if target_cur.rowcount > 0:
                migrated_count += 1
            else:
                skipped_count += 1
            
            # Progress indicator
            if i % 100 == 0:
                print(f"[PROGRESS] Processed {i}/{total_rows} rows...")
                
        except Exception as e:
            print(f"[ERROR] Failed to insert row {i}: {e}")
            skipped_count += 1
    
    target_conn.commit()
    
    print(f"[TARGET] Migrated {migrated_count} rows")
    print(f"[TARGET] Skipped {skipped_count} rows (already exist or errors)")
    
    return (total_rows, migrated_count, skipped_count)


def verify_migration(source_conn, target_conn, table_name: str) -> bool:
    """Verify that row counts match between source and target."""
    source_cur = source_conn.cursor()
    target_cur = target_conn.cursor()
    
    source_cur.execute(f"SELECT COUNT(*) FROM {table_name}")
    source_count = source_cur.fetchone()[0]
    
    target_cur.execute(f"SELECT COUNT(*) FROM {table_name}")
    target_count = target_cur.fetchone()[0]
    
    print(f"\n[VERIFY] {table_name}:")
    print(f"  Source: {source_count} rows")
    print(f"  Target: {target_count} rows")
    
    if source_count == target_count:
        print(f"  ✅ Match!")
        return True
    else:
        print(f"  ⚠️  Mismatch (difference: {source_count - target_count})")
        return False


def main():
    """Main migration process."""
    print("\n" + "="*60)
    print("PostgreSQL Data Migration Script")
    print("="*60)
    
    # Validate configuration
    if "username:password" in SOURCE_DB or "username:password" in TARGET_DB:
        print("\n[ERROR] Please edit the SOURCE_DB and TARGET_DB connection strings")
        print("        Replace 'username:password@localhost:5432/database_name' with actual values")
        return
    
    print(f"\nSource: {SOURCE_DB.split('@')[1] if '@' in SOURCE_DB else 'N/A'}")
    print(f"Target: {TARGET_DB.split('@')[1] if '@' in TARGET_DB else 'N/A'}")
    
    # Confirm before proceeding
    print("\n⚠️  WARNING: This will copy data from source to target database.")
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
        
        # Define table schemas with JSON columns
        tables_to_migrate = {
            "dynamic_skills": {
                "columns": [
                    "id", "name", "description", "requires", "produces", 
                    "optional_produces", "executor", "hitl_enabled", "prompt", 
                    "system_prompt", "rest_config", "action_config", "action_code",
                    "action_functions", "created_at", "updated_at", "created_by", 
                    "source", "enabled"
                ],
                "json_columns": ["requires", "produces", "optional_produces", "rest_config", "action_config"]
            },
            "run_metadata": {
                "columns": [
                    "id", "thread_id", "run_name", "sop", "initial_data",
                    "created_at", "parent_thread_id", "rerun_count", "metadata",
                    "status", "error_message", "failed_skill", "completed_at", "user_id"
                ],
                "json_columns": ["initial_data", "metadata"]
            }
        }
        
        # Migration statistics
        migration_stats = {}
        
        # Migrate each table
        for table_name, table_config in tables_to_migrate.items():
            total, migrated, skipped = migrate_table(
                source_conn, 
                target_conn, 
                table_name, 
                table_config["columns"],
                json_columns=table_config["json_columns"],
                skip_existing=True
            )
            migration_stats[table_name] = {
                "total": total,
                "migrated": migrated,
                "skipped": skipped
            }
        
        # Verify migrations
        print("\n" + "="*60)
        print("Verification")
        print("="*60)
        
        all_verified = True
        for table_name in tables_to_migrate.keys():
            verified = verify_migration(source_conn, target_conn, table_name)
            if not verified:
                all_verified = False
        
        # Summary
        print("\n" + "="*60)
        print("Migration Summary")
        print("="*60)
        
        for table_name, stats in migration_stats.items():
            print(f"\n{table_name}:")
            print(f"  Total rows in source: {stats['total']}")
            print(f"  Rows migrated: {stats['migrated']}")
            print(f"  Rows skipped: {stats['skipped']}")
        
        if all_verified:
            print("\n✅ All tables verified successfully!")
        else:
            print("\n⚠️  Some tables have count mismatches - please review")
        
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
