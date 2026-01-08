#!/usr/bin/env python3
"""
Cleanup script - Remove all workflow runs and logs from the database.

WARNING: This permanently deletes ALL workflow data!
- All workflow runs (checkpoints)
- All execution history
- All logs

Use this to start fresh during development.
DO NOT run this in production without backups!
"""
import os
import sys
from pathlib import Path

# Add parent directory to path to import env_loader
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from env_loader import load_env_once
import psycopg


def show_counts(cur):
    """Display current record counts."""
    cur.execute("SELECT COUNT(*) FROM checkpoints")
    checkpoint_count = cur.fetchone()[0]
    
    cur.execute("SELECT COUNT(*) FROM thread_logs")
    log_count = cur.fetchone()[0]
    
    cur.execute("SELECT COUNT(*) FROM checkpoint_blobs")
    blob_count = cur.fetchone()[0]
    
    cur.execute("SELECT COUNT(*) FROM checkpoint_writes")
    write_count = cur.fetchone()[0]
    
    return checkpoint_count, log_count, blob_count, write_count


def cleanup_database():
    """Clean up all workflow runs and logs."""
    print("\n" + "="*60)
    print("DATABASE CLEANUP - REMOVE ALL RUNS AND LOGS")
    print("="*60)
    
    # Load environment variables
    load_env_once(Path(__file__).resolve().parent.parent)
    
    db_uri = os.getenv("DATABASE_URL")
    if not db_uri:
        print("\n✗ ERROR: DATABASE_URL not set in environment")
        sys.exit(1)
    
    print("\n⚠️  WARNING: This will permanently delete:")
    print("   • All workflow runs (checkpoints)")
    print("   • All execution history")
    print("   • All thread logs")
    print("   • All pending writes and blobs")
    
    try:
        with psycopg.connect(db_uri, autocommit=True) as conn:
            with conn.cursor() as cur:
                # Show current state
                checkpoint_count, log_count, blob_count, write_count = show_counts(cur)
                
                print("\n" + "="*60)
                print("Current database state:")
                print("="*60)
                print(f"  Checkpoints:       {checkpoint_count:,}")
                print(f"  Thread logs:       {log_count:,}")
                print(f"  Checkpoint blobs:  {blob_count:,}")
                print(f"  Checkpoint writes: {write_count:,}")
                print("="*60)
                
                if checkpoint_count == 0 and log_count == 0:
                    print("\n✓ Database is already clean!")
                    return
                
                # Confirmation
                print("\n⚠️  Are you sure you want to delete ALL this data?")
                response = input("Type 'DELETE ALL' to confirm (or anything else to cancel): ")
                
                if response.strip() != "DELETE ALL":
                    print("\n✓ Cleanup cancelled. No data was deleted.")
                    return
                
                print("\n🗑️  Deleting all records...")
                
                # Delete in correct order (respecting foreign keys)
                print("  • Deleting checkpoint writes...")
                cur.execute("TRUNCATE TABLE checkpoint_writes CASCADE")
                
                print("  • Deleting checkpoint blobs...")
                cur.execute("TRUNCATE TABLE checkpoint_blobs CASCADE")
                
                print("  • Deleting checkpoints...")
                cur.execute("TRUNCATE TABLE checkpoints CASCADE")
                
                print("  • Deleting thread logs...")
                cur.execute("TRUNCATE TABLE thread_logs")
                
                # Reset sequences
                print("  • Resetting sequences...")
                cur.execute("ALTER SEQUENCE IF EXISTS thread_logs_id_seq RESTART WITH 1")
                
                # Verify cleanup
                checkpoint_count, log_count, blob_count, write_count = show_counts(cur)
                
                print("\n" + "="*60)
                print("✓ Cleanup complete!")
                print("="*60)
                print(f"  Checkpoints:       {checkpoint_count:,}")
                print(f"  Thread logs:       {log_count:,}")
                print(f"  Checkpoint blobs:  {blob_count:,}")
                print(f"  Checkpoint writes: {write_count:,}")
                print("="*60)
                print("\n✓ Database is now clean and ready for fresh runs!\n")
                
    except Exception as e:
        print(f"\n✗ ERROR: Failed to cleanup database: {e}")
        sys.exit(1)


if __name__ == "__main__":
    cleanup_database()

