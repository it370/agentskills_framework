#!/usr/bin/env python3
"""
Apply the thread_logs schema to the PostgreSQL database.
Run this script to create the logs table and indexes.
"""
import os
import sys
from pathlib import Path

# Add parent directory to path to import env_loader
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from env_loader import load_env_once
import psycopg


def apply_logs_schema():
    """Apply the logs schema to the database."""
    # Load environment variables
    load_env_once(Path(__file__).resolve().parent.parent)
    
    db_uri = os.getenv("DATABASE_URL")
    if not db_uri:
        print("ERROR: DATABASE_URL not set in environment")
        sys.exit(1)
    
    # Read schema file
    schema_file = Path(__file__).parent / "logs_schema.sql"
    if not schema_file.exists():
        print(f"ERROR: Schema file not found: {schema_file}")
        sys.exit(1)
    
    schema_sql = schema_file.read_text()
    
    print(f"Connecting to database...")
    try:
        with psycopg.connect(db_uri, autocommit=True) as conn:
            with conn.cursor() as cur:
                print("Applying logs schema...")
                cur.execute(schema_sql)
                print("✓ Logs schema applied successfully!")
                
                # Verify table was created
                cur.execute("""
                    SELECT COUNT(*) FROM information_schema.tables 
                    WHERE table_name = 'thread_logs'
                """)
                count = cur.fetchone()[0]
                
                if count > 0:
                    print("✓ thread_logs table verified")
                else:
                    print("⚠ Warning: thread_logs table not found after creation")
                
    except Exception as e:
        print(f"ERROR: Failed to apply schema: {e}")
        sys.exit(1)


if __name__ == "__main__":
    apply_logs_schema()

