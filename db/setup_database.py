#!/usr/bin/env python3
"""
Apply all database schemas and views.
Run this after initial database setup or when updating schema.
"""
import os
import sys
from pathlib import Path

# Add parent directory to path to import env_loader
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from env_loader import load_env_once
import psycopg


def apply_schema(conn, schema_file: Path, description: str):
    """Apply a single schema file."""
    if not schema_file.exists():
        print(f"⚠ Warning: {schema_file.name} not found, skipping")
        return False
    
    print(f"\n{'='*60}")
    print(f"Applying: {description}")
    print(f"{'='*60}")
    
    schema_sql = schema_file.read_text()
    
    try:
        with conn.cursor() as cur:
            cur.execute(schema_sql)
            print(f"✓ {description} applied successfully")
            return True
    except Exception as e:
        print(f"✗ Failed to apply {description}: {e}")
        return False


def main():
    """Apply all database schemas and views."""
    print("\n" + "="*60)
    print("Database Schema Setup")
    print("="*60)
    
    # Load environment variables
    load_env_once(Path(__file__).resolve().parent.parent)
    
    db_uri = os.getenv("DATABASE_URL")
    if not db_uri:
        print("\n✗ ERROR: DATABASE_URL not set in environment")
        sys.exit(1)
    
    db_dir = Path(__file__).parent
    
    schemas = [
        (db_dir / "checkpoints_schema.sql", "Checkpoints schema (LangGraph)"),
        (db_dir / "logs_schema.sql", "Thread logs schema"),
        (db_dir / "run_metadata_schema.sql", "Run metadata schema (for reruns)"),
        (db_dir / "run_list_view.sql", "Run list view with computed status"),
    ]
    
    print(f"\nConnecting to database...")
    success_count = 0
    total_count = len(schemas)
    
    try:
        with psycopg.connect(db_uri, autocommit=True) as conn:
            print(f"✓ Connected successfully")
            
            for schema_file, description in schemas:
                if apply_schema(conn, schema_file, description):
                    success_count += 1
            
            # Summary
            print(f"\n{'='*60}")
            print(f"Summary: {success_count}/{total_count} schemas applied successfully")
            print(f"{'='*60}")
            
            # Verify key tables and views
            print(f"\nVerifying database objects...")
            with conn.cursor() as cur:
                # Check tables
                cur.execute("""
                    SELECT table_name 
                    FROM information_schema.tables 
                    WHERE table_schema = 'public' 
                    AND table_type = 'BASE TABLE'
                    ORDER BY table_name
                """)
                tables = [row[0] for row in cur.fetchall()]
                print(f"✓ Tables: {', '.join(tables)}")
                
                # Check views
                cur.execute("""
                    SELECT table_name 
                    FROM information_schema.views 
                    WHERE table_schema = 'public'
                    ORDER BY table_name
                """)
                views = [row[0] for row in cur.fetchall()]
                print(f"✓ Views: {', '.join(views) if views else '(none)'}")
                
                # Check thread_logs count
                if 'thread_logs' in tables:
                    cur.execute("SELECT COUNT(*) FROM thread_logs")
                    log_count = cur.fetchone()[0]
                    print(f"✓ thread_logs: {log_count} log entries")
                
                # Check run_list_view count
                if 'run_list_view' in views:
                    cur.execute("SELECT COUNT(*) FROM run_list_view")
                    run_count = cur.fetchone()[0]
                    print(f"✓ run_list_view: {run_count} runs")
            
            print(f"\n{'='*60}")
            print("✓ Database setup complete!")
            print(f"{'='*60}\n")
            
            if success_count < total_count:
                print(f"⚠ Warning: Some schemas failed to apply")
                sys.exit(1)
                
    except Exception as e:
        print(f"\n✗ ERROR: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()

