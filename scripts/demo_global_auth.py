#!/usr/bin/env python3
"""
Demo: Global Auth Context

Shows how to initialize auth once at startup and use it everywhere.
"""

import asyncio
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Load .env file using project's env_loader (loads once)
from env_loader import load_env_once
load_env_once()

from services.credentials import (
    AuthContext, 
    get_system_user, 
    get_current_user,
    get_vault
)

def initialize_app():
    """Initialize application with global auth context."""
    print("=" * 70)
    print("Initializing Application")
    print("=" * 70)
    
    # Initialize global auth context (do this once at startup)
    auth = AuthContext.initialize(get_system_user())
    
    current_user = auth.get_current_user()
    print(f"\n✓ Global auth initialized")
    print(f"  User ID: {current_user.user_id}")
    print(f"  Username: {current_user.username}")
    print(f"  Roles: {current_user.roles}")
    
    return auth


async def setup_example_credential():
    """Setup example credential using global auth."""
    print("\n" + "=" * 70)
    print("Setting Up Example Credential")
    print("=" * 70)
    
    # Get current user from global context - no need to pass it!
    user = get_current_user()
    print(f"\n✓ Got user from global context: {user.user_id}")
    
    vault = get_vault()
    
    try:
        cred_id = vault.store_credential(
            user_context=user,  # From global context
            name="example_global_db",
            db_type="postgres",
            host="localhost",
            port=5432,
            database="example_db",
            username="app_user",
            password="secure_password_123",
            description="Example using global auth context"
        )
        print(f"✓ Stored credential: {cred_id}")
    except Exception as e:
        print(f"Note: {e}")


def use_auth_anywhere():
    """Show that you can access auth context from anywhere."""
    print("\n" + "=" * 70)
    print("Accessing Auth Context from Anywhere")
    print("=" * 70)
    
    # No need to pass user around - just get it!
    user = get_current_user()
    
    print(f"\n✓ Current user accessed from anywhere:")
    print(f"  User ID: {user.user_id}")
    print(f"  Is Admin: {user.is_admin()}")


async def simulate_skill_execution():
    """Simulate executing a skill with automatic auth."""
    print("\n" + "=" * 70)
    print("Simulating Skill Execution")
    print("=" * 70)
    
    print("\nOLD WAY (still works):")
    print("""
    result = await execute_skill(
        skill_name="DatabaseUserFetcher",
        inputs={
            "user_id": 123,
            "user_context": get_system_user()  # Had to pass explicitly
        }
    )
    """)
    
    print("\nNEW WAY (automatic):")
    print("""
    result = await execute_skill(
        skill_name="DatabaseUserFetcher",
        inputs={
            "user_id": 123
            # user_context automatically from AuthContext!
        }
    )
    """)
    
    print("\n✓ Engine automatically gets user from AuthContext")
    print("✓ No need to pass user_context in every skill execution")
    
    # Get user to show it's available
    user = get_current_user()
    vault = get_vault()
    
    # List credentials (using global auth)
    creds = vault.list_credentials(user)
    if creds:
        print(f"\n✓ Found {len(creds)} credential(s) for user {user.user_id}:")
        for cred in creds:
            print(f"  - {cred.name}: {cred.db_type} @ {cred.host}")


async def cleanup():
    """Cleanup example credentials."""
    print("\n" + "=" * 70)
    print("Cleanup")
    print("=" * 70)
    
    user = get_current_user()
    vault = get_vault()
    
    creds = vault.list_credentials(user)
    for cred in creds:
        if cred.name == "example_global_db":
            vault.delete_credential(user, cred.name)
            print(f"✓ Deleted example credential: {cred.name}")


async def main():
    # 1. Initialize app (do this once at startup)
    initialize_app()
    
    # 2. Setup credential
    await setup_example_credential()
    
    # 3. Show you can access auth anywhere
    use_auth_anywhere()
    
    # 4. Simulate skill execution
    await simulate_skill_execution()
    
    # 5. Cleanup
    await cleanup()
    
    # Summary
    print("\n" + "=" * 70)
    print("Summary: Global Auth Context Benefits")
    print("=" * 70)
    print("""
    ✅ Initialize once at startup
    ✅ Access anywhere with get_current_user()
    ✅ No need to pass user_context everywhere
    ✅ Skills automatically use global auth
    ✅ Cleaner, simpler code
    ✅ Easy to migrate to real auth later
    
    Key Pattern:
    
    # In main.py (startup):
    from services.credentials import AuthContext, get_system_user
    AuthContext.initialize(get_system_user())
    
    # Anywhere else:
    from services.credentials import get_current_user
    user = get_current_user()  # That's it!
    
    # Skills execute without user_context in inputs:
    result = await execute_skill(
        skill_name="DatabaseUserFetcher",
        inputs={"user_id": 123}  # No user_context needed!
    )
    """)
    
    print("\nFor more info:")
    print("  - documentations/GLOBAL_AUTH_CONTEXT.md")
    print("  - services/credentials/auth_context.py")


if __name__ == "__main__":
    asyncio.run(main())
