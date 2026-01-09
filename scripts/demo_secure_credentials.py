#!/usr/bin/env python3
"""
Example: Using secure credentials for skill-local database configurations.

This example demonstrates:
1. Creating a user context
2. Storing secure database credentials
3. Creating a skill that uses those credentials
4. Running the skill with automatic credential resolution
"""

import asyncio
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Load .env file using project's env_loader (loads once)
from env_loader import load_env_once
load_env_once()

from services.credentials import get_vault, UserContext, CredentialNotFoundError


async def main():
    print("=" * 70)
    print("Secure Credential Management Example")
    print("=" * 70)
    
    # =========================================================================
    # Step 1: Create a user context
    # =========================================================================
    print("\n[Step 1] Creating user context...")
    
    user_alice = UserContext(
        user_id="alice_001",
        username="alice@example.com",
        roles=["user"]
    )
    
    user_bob = UserContext(
        user_id="bob_002",
        username="bob@example.com",
        roles=["user"]
    )
    
    print(f"  ✓ Created user: {user_alice.username}")
    print(f"  ✓ Created user: {user_bob.username}")
    
    # =========================================================================
    # Step 2: Store secure database credentials
    # =========================================================================
    print("\n[Step 2] Storing secure credentials...")
    
    vault = get_vault()
    
    # Alice stores her database credential
    alice_cred_id = vault.store_credential(
        user_context=user_alice,
        name="my_postgres_main",
        db_type="postgres",
        host="alice-db.example.com",
        port=5432,
        database="alice_production",
        username="alice_db_user",
        password="alice_super_secret_password_123",
        description="Alice's main production database"
    )
    print(f"  ✓ Alice stored credential: {alice_cred_id}")
    
    # Bob stores his database credential
    bob_cred_id = vault.store_credential(
        user_context=user_bob,
        name="my_postgres_main",
        db_type="postgres",
        host="bob-db.example.com",
        port=5432,
        database="bob_production",
        username="bob_db_user",
        password="bob_super_secret_password_456",
        description="Bob's main production database"
    )
    print(f"  ✓ Bob stored credential: {bob_cred_id}")
    
    # =========================================================================
    # Step 3: List credentials (user-isolated)
    # =========================================================================
    print("\n[Step 3] Listing credentials (user-isolated)...")
    
    alice_creds = vault.list_credentials(user_alice)
    print(f"  Alice's credentials: {[c.name for c in alice_creds]}")
    
    bob_creds = vault.list_credentials(user_bob)
    print(f"  Bob's credentials: {[c.name for c in bob_creds]}")
    
    # =========================================================================
    # Step 4: Demonstrate user isolation (security)
    # =========================================================================
    print("\n[Step 4] Testing user isolation...")
    
    # Alice can access her own credential
    try:
        alice_cred = vault.get_credential(user_alice, "my_postgres_main")
        print(f"  ✓ Alice accessed her credential: {alice_cred.name}")
    except Exception as e:
        print(f"  ✗ Alice failed to access her credential: {e}")
    
    # Bob cannot access Alice's credential
    try:
        vault.get_credential(user_bob, alice_cred_id)
        print(f"  ✗ SECURITY ISSUE: Bob accessed Alice's credential!")
    except CredentialNotFoundError:
        print(f"  ✓ Security working: Bob cannot access Alice's credential")
    except Exception as e:
        print(f"  ✓ Security working: {type(e).__name__}")
    
    # =========================================================================
    # Step 5: Build connection string (password decrypted in memory only)
    # =========================================================================
    print("\n[Step 5] Building connection strings...")
    
    alice_cred = vault.get_credential(user_alice, "my_postgres_main")
    alice_conn_str = vault.build_connection_string(alice_cred)
    
    # Show masked connection string
    masked = alice_conn_str.replace(
        vault.get_decrypted_password(alice_cred),
        "****"
    )
    print(f"  Alice's connection: {masked}")
    print(f"  (Password decrypted in memory only, never stored in plain text)")
    
    # =========================================================================
    # Step 6: Update password (credential rotation)
    # =========================================================================
    print("\n[Step 6] Rotating credentials...")
    
    vault.update_password(
        user_context=user_alice,
        credential_ref="my_postgres_main",
        new_password="alice_new_password_789"
    )
    print(f"  ✓ Alice's password rotated")
    print(f"  Note: Skills using this credential automatically get new password")
    
    # =========================================================================
    # Step 7: Demonstrate skill usage
    # =========================================================================
    print("\n[Step 7] Skill usage example...")
    print("""
    In your skill (DatabaseUserFetcher/skill.md):
    
    ```yaml
    action:
      type: data_query
      source: postgres
      query: "SELECT * FROM users WHERE id = {user_id}"
      credential_ref: "my_postgres_main"  # Direct reference - simple!
    ```
    
    When executing the skill:
    ```python
    result = await execute_skill(
        skill_name="DatabaseUserFetcher",
        inputs={
            "user_id": 123,
            "user_context": user_alice  # Required for credential resolution
        }
    )
    ```
    
    Framework automatically:
    1. Reads credential_ref from action config
    2. Checks authorization (user_context)
    3. Retrieves credential from vault
    4. Decrypts password
    5. Builds connection string
    6. Executes query
    7. Returns results
    
    That's it - no separate config files needed!
    """)
    
    # =========================================================================
    # Step 8: Clean up
    # =========================================================================
    print("\n[Step 8] Cleaning up...")
    
    vault.delete_credential(user_alice, "my_postgres_main")
    print(f"  ✓ Deleted Alice's credential")
    
    vault.delete_credential(user_bob, "my_postgres_main")
    print(f"  ✓ Deleted Bob's credential")
    
    # =========================================================================
    # Summary
    # =========================================================================
    print("\n" + "=" * 70)
    print("Summary: Secure Credential Benefits")
    print("=" * 70)
    print("""
    ✅ Passwords encrypted at rest (AES-256)
    ✅ User isolation - cannot access others' credentials
    ✅ Password rotation without changing skills
    ✅ Audit trail of credential access
    ✅ Portable skills - share without exposing secrets
    ✅ Multi-user safe - each user has own credential namespace
    ✅ Admin support - admins can manage all credentials
    """)
    
    print("\nFor more information, see:")
    print("  - documentations/SECURE_CREDENTIALS.md")
    print("  - services/credentials/")
    

if __name__ == "__main__":
    asyncio.run(main())
