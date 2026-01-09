#!/usr/bin/env python3
"""
Quick example: Using credentials without user authentication.

This shows how to use the secure credential system when you don't
have user authentication set up yet.
"""

import asyncio
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Load .env file using project's env_loader (loads once)
from env_loader import load_env_once
load_env_once()

from services.credentials import get_vault, get_system_user

async def main():
    print("=" * 70)
    print("Using Credentials Without User Authentication")
    print("=" * 70)
    
    # Get system user (default user for apps without auth)
    system_user = get_system_user()
    print(f"\n✓ Using system user: {system_user.user_id}")
    print(f"  Username: {system_user.username}")
    print(f"  Roles: {system_user.roles}")
    
    # Get vault
    vault = get_vault()
    
    # Example 1: Store a credential
    print("\n[Example 1] Storing a credential...")
    try:
        cred_id = vault.store_credential(
            user_context=system_user,
            name="example_db",
            db_type="postgres",
            host="localhost",
            port=5432,
            database="example_db",
            username="db_user",
            password="db_password_123",
            description="Example database for testing"
        )
        print(f"✓ Stored credential: {cred_id}")
    except Exception as e:
        print(f"Note: {e}")
    
    # Example 2: List credentials
    print("\n[Example 2] Listing credentials...")
    credentials = vault.list_credentials(system_user)
    if credentials:
        for cred in credentials:
            print(f"  - {cred.name}: {cred.db_type} @ {cred.host}:{cred.port}/{cred.database}")
    else:
        print("  No credentials found")
    
    # Example 3: Get a credential
    print("\n[Example 3] Retrieving a credential...")
    if credentials:
        cred_name = credentials[0].name
        credential = vault.get_credential(system_user, cred_name)
        conn_str = vault.build_connection_string(credential)
        
        # Mask password for display
        password = vault.get_decrypted_password(credential)
        masked_conn = conn_str.replace(password, "****")
        
        print(f"✓ Retrieved credential: {cred_name}")
        print(f"  Connection: {masked_conn}")
    
    # Example 4: Usage in skill execution
    print("\n[Example 4] Using in skill execution...")
    print("""
    When executing a skill that needs database access:
    
    ```python
    from services.credentials import get_system_user
    
    # Get system user
    system_user = get_system_user()
    
    # Execute skill
    result = await execute_skill(
        skill_name="DatabaseUserFetcher",
        inputs={{
            "user_id": 123,
            "user_context": system_user  # Always use system_user
        }}
    )
    ```
    
    Your skill.md:
    ```yaml
    action:
      type: data_query
      source: postgres
      credential_ref: "example_db"  # References the credential we created
      query: "SELECT * FROM users WHERE id = {{user_id}}"
    ```
    
    That's it! The framework will:
    1. Get the credential reference from action config
    2. Retrieve "example_db" credential from vault
    3. Check that system_user owns it (or is admin)
    4. Decrypt the password
    5. Build connection string
    6. Execute the query
    """)
    
    # Clean up
    print("\n[Cleanup]")
    if credentials:
        for cred in credentials:
            if cred.name == "example_db":
                vault.delete_credential(system_user, cred.name)
                print(f"✓ Deleted example credential: {cred.name}")
    
    print("\n" + "=" * 70)
    print("Summary")
    print("=" * 70)
    print("""
    For apps without user authentication:
    
    1. Use `get_system_user()` everywhere
    2. Store credentials with CLI:
       python -m scripts.credential_manager add --user system --name my_db
    
    3. In your code:
       from services.credentials import get_system_user
       user = get_system_user()
       
    4. Pass user to skill execution:
       inputs["user_context"] = user
    
    5. Reference credential in skill.md:
       credential_ref: "my_db"
    
    Benefits:
    ✓ Passwords encrypted (AES-256)
    ✓ Credential rotation without code changes
    ✓ Easy to add multi-user support later
    ✓ No passwords in code or config files
    """)
    print("\nFor more info, see: documentations/CREDENTIALS_WITHOUT_AUTH.md")

if __name__ == "__main__":
    asyncio.run(main())
