#!/usr/bin/env python3
"""
CLI tool for managing secure database credentials.

Usage:
    python -m scripts.credential_manager add --user alice --name my_db
    python -m scripts.credential_manager list --user alice
    python -m scripts.credential_manager update --user alice --name my_db
    python -m scripts.credential_manager delete --user alice --name my_db
"""

import argparse
import sys
import getpass
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Load .env file using project's env_loader (loads once)
from env_loader import load_env_once
load_env_once()

from services.credentials import get_vault, UserContext, CredentialNotFoundError


def cmd_add(args):
    """Add a new credential."""
    print(f"Adding credential '{args.name}' for user {args.user}")
    print()
    
    # Get database details
    db_type = args.db_type or input("Database type (postgres/mysql/mongodb): ").strip()
    host = args.host or input("Host: ").strip()
    port = args.port or int(input(f"Port (default {_default_port(db_type)}): ").strip() or _default_port(db_type))
    database = args.database or input("Database name: ").strip()
    username = args.username or input("Username: ").strip()
    
    # Get password securely
    if args.password:
        password = args.password
        print("WARNING: Passing password via command line is insecure!")
    else:
        password = getpass.getpass("Password: ")
        password_confirm = getpass.getpass("Confirm password: ")
        
        if password != password_confirm:
            print("ERROR: Passwords do not match!")
            return 1
    
    description = args.description or input("Description (optional): ").strip() or None
    
    # Store credential
    vault = get_vault()
    user_context = UserContext(
        user_id=args.user,
        username=args.user,
        roles=args.roles.split(',') if args.roles else ["user"]
    )
    
    try:
        cred_id = vault.store_credential(
            user_context=user_context,
            name=args.name,
            db_type=db_type,
            host=host,
            port=port,
            database=database,
            username=username,
            password=password,
            description=description
        )
        
        print()
        print(f"SUCCESS: Credential stored successfully!")
        print(f"   Credential ID: {cred_id}")
        print(f"   Name: {args.name}")
        print(f"   Type: {db_type}")
        print(f"   Host: {host}:{port}")
        print(f"   Database: {database}")
        print()
        print("Use in skill.md by adding to action config:")
        print(f"""   action:
     type: data_query
     source: postgres
     credential_ref: "{args.name}"
     query: "SELECT ..."
""")
        
        return 0
    except Exception as e:
        print(f"ERROR: Failed to store credential: {e}")
        return 1


def cmd_list(args):
    """List credentials for a user."""
    vault = get_vault()
    user_context = UserContext(
        user_id=args.user,
        username=args.user,
        roles=args.roles.split(',') if args.roles else ["user"]
    )
    
    try:
        credentials = vault.list_credentials(user_context)
        
        if not credentials:
            print(f"No credentials found for user {args.user}")
            return 0
        
        print(f"\nCredentials for user {args.user}:")
        print("=" * 80)
        
        for cred in credentials:
            print(f"\n📁 {cred.name}")
            print(f"   ID:          {cred.credential_id}")
            print(f"   Type:        {cred.db_type}")
            print(f"   Host:        {cred.host}:{cred.port}")
            print(f"   Database:    {cred.database}")
            print(f"   Username:    {cred.username}")
            print(f"   Created:     {cred.created_at.isoformat()}")
            print(f"   Updated:     {cred.updated_at.isoformat()}")
            if cred.description:
                print(f"   Description: {cred.description}")
        
        print("\n" + "=" * 80)
        print(f"Total: {len(credentials)} credential(s)")
        
        return 0
    except Exception as e:
        print(f"ERROR: Failed to list credentials: {e}")
        return 1


def cmd_update(args):
    """Update credential password."""
    print(f"Updating password for '{args.name}' (user: {args.user})")
    
    vault = get_vault()
    user_context = UserContext(
        user_id=args.user,
        username=args.user,
        roles=args.roles.split(',') if args.roles else ["user"]
    )
    
    # Get new password
    if args.password:
        new_password = args.password
        print("WARNING: Passing password via command line is insecure!")
    else:
        new_password = getpass.getpass("New password: ")
        password_confirm = getpass.getpass("Confirm new password: ")
        
        if new_password != password_confirm:
            print("ERROR: Passwords do not match!")
            return 1
    
    try:
        vault.update_password(user_context, args.name, new_password)
        print(f"SUCCESS: Password updated successfully for '{args.name}'")
        print("   Skills using this credential will automatically use the new password")
        return 0
    except CredentialNotFoundError:
        print(f"ERROR: Credential '{args.name}' not found for user {args.user}")
        return 1
    except Exception as e:
        print(f"ERROR: Failed to update password: {e}")
        return 1


def cmd_delete(args):
    """Delete a credential."""
    print(f"Deleting credential '{args.name}' for user {args.user}")
    
    if not args.yes:
        confirm = input(f"Are you sure you want to delete '{args.name}'? (yes/no): ").strip().lower()
        if confirm != "yes":
            print("Cancelled.")
            return 0
    
    vault = get_vault()
    user_context = UserContext(
        user_id=args.user,
        username=args.user,
        roles=args.roles.split(',') if args.roles else ["user"]
    )
    
    try:
        vault.delete_credential(user_context, args.name)
        print(f"SUCCESS: Credential '{args.name}' deleted successfully")
        print("   WARNING: Skills using this credential will no longer work!")
        return 0
    except CredentialNotFoundError:
        print(f"ERROR: Credential '{args.name}' not found for user {args.user}")
        return 1
    except Exception as e:
        print(f"ERROR: Failed to delete credential: {e}")
        return 1


def cmd_test(args):
    """Test credential by building connection string."""
    vault = get_vault()
    user_context = UserContext(
        user_id=args.user,
        username=args.user,
        roles=args.roles.split(',') if args.roles else ["user"]
    )
    
    try:
        credential = vault.get_credential(user_context, args.name)
        conn_str = vault.build_connection_string(credential)
        
        # Mask password
        password = vault.get_decrypted_password(credential)
        masked_conn_str = conn_str.replace(password, "****")
        
        print(f"\n✅ Credential '{args.name}' is valid")
        print(f"   Connection string: {masked_conn_str}")
        print(f"   Type: {credential.db_type}")
        print(f"   Host: {credential.host}:{credential.port}")
        print(f"   Database: {credential.database}")
        
        return 0
    except CredentialNotFoundError:
        print(f"ERROR: Credential '{args.name}' not found for user {args.user}")
        return 1
    except Exception as e:
        print(f"ERROR: Failed to test credential: {e}")
        return 1


def cmd_show(args):
    """Show credential with plaintext password (DEV/TEST ONLY!)."""
    print("=" * 70)
    print("WARNING: DISPLAYING PLAINTEXT PASSWORD - DEV/TEST ONLY!")
    print("=" * 70)
    print()
    
    vault = get_vault()
    user_context = UserContext(
        user_id=args.user,
        username=args.user,
        roles=args.roles.split(',') if args.roles else ["user"]
    )
    
    try:
        credential = vault.get_credential(user_context, args.name)
        password = vault.get_decrypted_password(credential)
        conn_str = vault.build_connection_string(credential)
        
        print(f"Credential: {credential.name}")
        print(f"  Type: {credential.db_type}")
        print(f"  Host: {credential.host}")
        print(f"  Port: {credential.port}")
        print(f"  Database: {credential.database}")
        print(f"  Username: {credential.username}")
        print(f"  Password: {password}")
        print()
        print(f"Connection String:")
        print(f"  {conn_str}")
        print()
        print(f"Description: {credential.description or 'None'}")
        
        return 0
    except CredentialNotFoundError:
        print(f"ERROR: Credential '{args.name}' not found for user {args.user}")
        return 1
    except Exception as e:
        print(f"ERROR: Failed to show credential: {e}")
        return 1


def _default_port(db_type: str) -> int:
    """Get default port for database type."""
    defaults = {
        "postgres": 5432,
        "mysql": 3306,
        "mongodb": 27017,
        "redis": 6379,
    }
    return defaults.get(db_type.lower(), 5432)


def main():
    parser = argparse.ArgumentParser(
        description="Manage secure database credentials for skills"
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Command to run")
    
    # Common arguments
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--user", required=True, help="User ID")
    common.add_argument("--roles", help="Comma-separated roles (default: user)")
    
    # Add command
    add_parser = subparsers.add_parser("add", parents=[common], help="Add a new credential")
    add_parser.add_argument("--name", required=True, help="Credential name")
    add_parser.add_argument("--db-type", help="Database type (postgres/mysql/mongodb)")
    add_parser.add_argument("--host", help="Database host")
    add_parser.add_argument("--port", type=int, help="Database port")
    add_parser.add_argument("--database", help="Database name")
    add_parser.add_argument("--username", help="Database username")
    add_parser.add_argument("--password", help="Database password (not recommended)")
    add_parser.add_argument("--description", help="Description")
    add_parser.set_defaults(func=cmd_add)
    
    # List command
    list_parser = subparsers.add_parser("list", parents=[common], help="List credentials")
    list_parser.set_defaults(func=cmd_list)
    
    # Update command
    update_parser = subparsers.add_parser("update", parents=[common], help="Update credential password")
    update_parser.add_argument("--name", required=True, help="Credential name")
    update_parser.add_argument("--password", help="New password (not recommended)")
    update_parser.set_defaults(func=cmd_update)
    
    # Delete command
    delete_parser = subparsers.add_parser("delete", parents=[common], help="Delete a credential")
    delete_parser.add_argument("--name", required=True, help="Credential name")
    delete_parser.add_argument("--yes", "-y", action="store_true", help="Skip confirmation")
    delete_parser.set_defaults(func=cmd_delete)
    
    # Test command
    test_parser = subparsers.add_parser("test", parents=[common], help="Test a credential")
    test_parser.add_argument("--name", required=True, help="Credential name")
    test_parser.set_defaults(func=cmd_test)
    
    # Show command (plaintext - dev only!)
    show_parser = subparsers.add_parser("show", parents=[common], help="Show credential with plaintext password (DEV/TEST ONLY!)")
    show_parser.add_argument("--name", required=True, help="Credential name")
    show_parser.set_defaults(func=cmd_show)
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return 1
    
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
