#!/usr/bin/env python3
"""
Apply the run_list_view to the PostgreSQL database.
This view provides enriched run data with computed status.
"""
import os
import sys
from pathlib import Path

# Add parent directory to path to import env_loader
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from env_loader import load_env_once
import psycopg


def apply_run_list_view():
    """Apply the run list view to the database."""
    # Load environment variables
    load_env_once(Path(__file__).resolve().parent.parent)
    
    db_uri = os.getenv("DATABASE_URL")
    if not db_uri:
        print("ERROR: DATABASE_URL not set in environment")
        sys.exit(1)
    
    # Read view file
    view_file = Path(__file__).parent / "run_list_view.sql"
    if not view_file.exists():
        print(f"ERROR: View file not found: {view_file}")
        sys.exit(1)
    
    view_sql = view_file.read_text()
    
    print(f"Connecting to database...")
    try:
        with psycopg.connect(db_uri, autocommit=True) as conn:
            with conn.cursor() as cur:
                print("Creating/replacing run_list_view...")
                cur.execute(view_sql)
                print("✓ run_list_view created successfully!")
                
                # Verify view was created
                cur.execute("""
                    SELECT COUNT(*) FROM information_schema.views 
                    WHERE table_name = 'run_list_view'
                """)
                count = cur.fetchone()[0]
                
                if count > 0:
                    print("✓ run_list_view verified")
                    
                    # Show sample data
                    cur.execute("SELECT COUNT(*) FROM run_list_view")
                    run_count = cur.fetchone()[0]
                    print(f"✓ View contains {run_count} run(s)")
                else:
                    print("⚠ Warning: run_list_view not found after creation")
                
    except Exception as e:
        print(f"ERROR: Failed to apply view: {e}")
        sys.exit(1)


if __name__ == "__main__":
    apply_run_list_view()

