"""
Apply user management database schema

This script creates the users, password_reset_tokens, and user_sessions tables,
and adds user_id tracking to run_metadata and logs tables.
"""

import os
import sys
from pathlib import Path

# Add parent directory to path BEFORE importing env_loader
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

import psycopg
from env_loader import load_env_once

# Load environment using centralized env loader
load_env_once(project_root)

DB_URI = os.getenv("DATABASE_URL")
if not DB_URI:
    print("ERROR: DATABASE_URL not set in environment")
    sys.exit(1)


def apply_schema(db_uri: str):
    """Apply user management schema and migrations"""
    print("[DB] Connecting to database...")
    
    with psycopg.connect(db_uri, autocommit=True) as conn:
        with conn.cursor() as cur:
            # Apply users schema
            print("[DB] Creating users tables...")
            users_schema = (project_root / "db" / "users_schema.sql").read_text()
            cur.execute(users_schema)
            print("[DB] ✓ Users tables created")
            
            # Apply user tracking migration
            print("[DB] Adding user tracking to existing tables...")
            migration = (project_root / "db" / "add_user_tracking_migration.sql").read_text()
            cur.execute(migration)
            print("[DB] ✓ User tracking added")
            
            # Create default system user if not exists
            print("[DB] Creating default system user...")
            cur.execute("""
                SELECT id FROM users WHERE username = 'system'
            """)
            if not cur.fetchone():
                # Generate a random password (should be changed immediately)
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
                print(f"[DB] ✓ System user created (ID: {user_id})")
                print(f"[DB] IMPORTANT: Default password for 'system': {default_password}")
                print(f"[DB] Please change this password immediately!")
            else:
                print("[DB] ✓ System user already exists")
    
    print("\n[DB] Schema applied successfully!")
    print("\nNext steps:")
    print("1. Set JWT_SECRET in your .env file")
    print("2. Optionally configure SMTP settings for password reset emails")
    print("3. Register users via /auth/register endpoint")
    print("4. Login via /auth/login endpoint")


if __name__ == "__main__":
    try:
        apply_schema(DB_URI)
    except Exception as e:
        print(f"[DB] ERROR: {e}")
        sys.exit(1)
