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


def apply_schema(conn, schema_file: Path, description: str, is_checkpoint_schema: bool = False):
    """Apply a single schema file."""
    if not schema_file.exists():
        print(f"WARNING: {schema_file.name} not found, skipping")
        return False
    
    print(f"\n{'='*60}")
    print(f"Applying: {description}")
    print(f"{'='*60}")
    
    schema_sql = schema_file.read_text()
    
    try:
        with conn.cursor() as cur:
            if is_checkpoint_schema:
                # Split and execute checkpoint schema in parts
                # Tables first (can be in transaction)
                tables_sql = []
                concurrent_indexes = []
                
                for line in schema_sql.split('\n'):
                    if 'CREATE INDEX CONCURRENTLY' in line.upper():
                        concurrent_indexes.append(line)
                    else:
                        tables_sql.append(line)
                
                # Execute table creation
                if tables_sql:
                    cur.execute('\n'.join(tables_sql))
                    print(f"[OK] Checkpoint tables created")
                
                # Execute concurrent indexes separately (already in autocommit mode)
                for idx_sql in concurrent_indexes:
                    if idx_sql.strip():
                        try:
                            cur.execute(idx_sql)
                        except Exception as idx_e:
                            # Ignore if index already exists
                            if "already exists" not in str(idx_e).lower():
                                print(f"[WARN] Index creation warning: {idx_e}")
                
                if concurrent_indexes:
                    print(f"[OK] Checkpoint indexes created")
            else:
                cur.execute(schema_sql)
            
            print(f"[OK] {description} applied successfully")
            return True
    except Exception as e:
        error_msg = str(e)
        # Schema may fail if already exists - that's okay
        if "already exists" in error_msg.lower():
            print(f"[SKIP] {description} already exists")
            return True  # Count as success
        print(f"[FAIL] Failed to apply {description}: {e}")
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
        print("\n[ERROR] DATABASE_URL not set in environment")
        sys.exit(1)
    
    db_dir = Path(__file__).parent
    
    # Schema files to apply in order
    # Note: Migrations are included for new installations
    # For existing databases, run migrations separately if needed
    schemas = [
        (db_dir / "checkpoints_schema.sql", "Checkpoints schema (LangGraph)", True),  # Special handling
        (db_dir / "logs_schema.sql", "Thread logs schema", False),
        (db_dir / "run_metadata_schema.sql", "Run metadata schema (for reruns)", False),
        (db_dir / "add_status_columns_migration.sql", "Status tracking columns (migration)", False),
        (db_dir / "add_run_name_migration.sql", "Run name column (migration)", False),
        (db_dir / "add_paused_status_migration.sql", "Paused status support (migration)", False),
        (db_dir / "dynamic_skills_schema.sql", "Dynamic skills schema (UI skill builder)", False),
        (db_dir / "add_action_functions_column.sql", "Action functions column (migration)", False),
        (db_dir / "users_schema.sql", "User management schema (authentication)", False),
        (db_dir / "workspaces_schema.sql", "Workspace schema (per-user isolation)", False),
        (db_dir / "add_user_tracking_migration.sql", "User tracking migration (user_id columns)", False),
        (db_dir / "add_workspace_columns_migration.sql", "Workspace isolation migration (skills & runs)", False),
        (db_dir / "add_workspace_code_migration.sql", "Workspace code (module namespace) migration", False),
        (db_dir / "update_dynamic_skill_module_prefix_migration.sql", "Namespace dynamic skill modules by workspace code", False),
        (db_dir / "fix_skill_name_uniqueness.sql", "CRITICAL: Fix skill name uniqueness per workspace", False),
        (db_dir / "remove_module_name_trigger.sql", "Remove module_name trigger (Python handles naming)", False),
        (db_dir / "migrate_to_uuid_and_module_name.sql", "UUID and module_name migration (IMPORTANT: Run manually first for existing DBs)", False),
        (db_dir / "run_list_view.sql", "Run list view with computed status", False),
    ]
    
    print(f"\nConnecting to database...")
    success_count = 0
    total_count = len(schemas)
    
    try:
        with psycopg.connect(db_uri, autocommit=True) as conn:
            print(f"[OK] Connected successfully")
            
            for schema_file, description, is_checkpoint in schemas:
                if apply_schema(conn, schema_file, description, is_checkpoint):
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
                print(f"[OK] Tables: {', '.join(tables)}")
                
                # Check views
                cur.execute("""
                    SELECT table_name 
                    FROM information_schema.views 
                    WHERE table_schema = 'public'
                    ORDER BY table_name
                """)
                views = [row[0] for row in cur.fetchall()]
                print(f"[OK] Views: {', '.join(views) if views else '(none)'}")
                
                # Check users count
                if 'users' in tables:
                    cur.execute("SELECT COUNT(*) FROM users")
                    user_count = cur.fetchone()[0]
                    print(f"[OK] users: {user_count} registered users")
                
                # Check thread_logs count
                if 'thread_logs' in tables:
                    cur.execute("SELECT COUNT(*) FROM thread_logs")
                    log_count = cur.fetchone()[0]
                    print(f"[OK] thread_logs: {log_count} log entries")
                
                # Check run_list_view count
                if 'run_list_view' in views:
                    cur.execute("SELECT COUNT(*) FROM run_list_view")
                    run_count = cur.fetchone()[0]
                    print(f"[OK] run_list_view: {run_count} runs")
            
            print(f"\n{'='*60}")
            print("[OK] Database setup complete!")
            print(f"{'='*60}\n")
            
            # Check if we should create default system user
            if 'users' in tables:
                with conn.cursor() as cur:
                    cur.execute("SELECT COUNT(*) FROM users WHERE username = 'system'")
                    system_user_exists = cur.fetchone()[0] > 0
                    
                    if not system_user_exists:
                        print("\n[USER] Creating default system user...")
                        try:
                            import secrets
                            import bcrypt
                            
                            default_password = secrets.token_urlsafe(16)
                            salt = bcrypt.gensalt()
                            hashed = bcrypt.hashpw(default_password.encode('utf-8'), salt)
                            
                            cur.execute("""
                                INSERT INTO users (username, email, password_hash, is_active, is_admin)
                                VALUES ('system', 'system@localhost', %s, TRUE, TRUE)
                                RETURNING id
                            """, (hashed.decode('utf-8'),))
                            
                            user_id = cur.fetchone()[0]
                            print(f"[USER] ✓ System user created (ID: {user_id})")
                            print(f"[USER] Default username: system")
                            print(f"[USER] Default password: {default_password}")
                            print(f"[USER] IMPORTANT: Please change this password immediately!")
                            print(f"[USER]            Login and use /auth/change-password endpoint\n")
                        except ImportError as imp_e:
                            print(f"[WARN] Could not create system user: {imp_e}")
                            print(f"       Install 'bcrypt' package: pip install bcrypt")
                            print(f"       Or run 'python db/apply_user_schema.py' to create it later\n")
                        except Exception as user_e:
                            print(f"[WARN] Could not create system user: {user_e}")
                            print(f"       Run 'python db/apply_user_schema.py' to create it later\n")
                    else:
                        print(f"[USER] ✓ System user already exists\n")
            
            if success_count < total_count:
                print(f"WARNING: Some schemas failed to apply")
                sys.exit(1)
                
    except Exception as e:
        print(f"\n[ERROR] {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()

