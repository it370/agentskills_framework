#!/usr/bin/env python3
"""
Diagnostic script to check AuthContext state.
Run this to see if AuthContext is properly initialized.
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from env_loader import load_env_once
load_env_once(Path(__file__).resolve().parent.parent)

def diagnose():
    """Diagnose AuthContext initialization state."""
    print("=" * 70)
    print("AuthContext Diagnostic Report")
    print("=" * 70)
    
    # Step 1: Check if credentials module is available
    print("\n[Step 1] Checking credentials module...")
    try:
        from services.credentials import AuthContext, get_current_user, get_vault
        print("✓ Credentials module imported successfully")
    except ImportError as e:
        print(f"✗ Failed to import credentials module: {e}")
        return
    
    # Step 2: Check if AuthContext is initialized
    print("\n[Step 2] Checking AuthContext initialization...")
    is_initialized = AuthContext.is_initialized()
    print(f"  Is initialized: {is_initialized}")
    
    if is_initialized:
        print("✓ AuthContext is initialized")
        try:
            current_user = AuthContext.get_current_user()
            print(f"  Current user ID: {current_user.user_id}")
            print(f"  Current username: {current_user.username}")
            print(f"  Current roles: {current_user.roles}")
            print(f"  Is admin: {current_user.is_admin()}")
        except Exception as e:
            print(f"✗ Failed to get current user: {e}")
    else:
        print("✗ AuthContext is NOT initialized")
        print("\n  Attempting to initialize from environment...")
        try:
            auth = AuthContext.initialize_from_env()
            print("✓ AuthContext initialized successfully")
            current_user = auth.get_current_user()
            print(f"  Current user ID: {current_user.user_id}")
            print(f"  Current username: {current_user.username}")
            print(f"  Current roles: {current_user.roles}")
            print(f"  Is admin: {current_user.is_admin()}")
        except Exception as e:
            print(f"✗ Failed to initialize AuthContext: {e}")
            return
    
    # Step 3: Check vault accessibility
    print("\n[Step 3] Checking credential vault...")
    try:
        vault = get_vault()
        print("✓ Vault instance obtained")
        
        # List credentials for current user
        current_user = get_current_user()
        credentials = vault.list_credentials(current_user)
        print(f"  Credentials for {current_user.user_id}: {len(credentials)} found")
        
        if credentials:
            print("\n  Available credentials:")
            for cred in credentials:
                print(f"    - {cred.name} (ID: {cred.credential_id})")
                print(f"      Type: {cred.db_type}")
                print(f"      Host: {cred.host}:{cred.port}")
                print(f"      User ID: {cred.user_id}")
        else:
            print("  ⚠ No credentials found for this user")
            print(f"    Run: python -m scripts.credential_manager add --user {current_user.user_id} --name <credential_name>")
        
    except Exception as e:
        print(f"✗ Failed to access vault: {e}")
        import traceback
        traceback.print_exc()
    
    # Step 4: Test get_current_user() function
    print("\n[Step 4] Testing get_current_user() function...")
    try:
        user = get_current_user()
        print("✓ get_current_user() works")
        print(f"  User ID: {user.user_id}")
    except RuntimeError as e:
        print(f"✗ get_current_user() failed: {e}")
    except Exception as e:
        print(f"✗ Unexpected error: {e}")
    
    # Step 5: Check environment variables
    print("\n[Step 5] Checking relevant environment variables...")
    import os
    
    env_vars = {
        "DEFAULT_USER_ID": os.getenv("DEFAULT_USER_ID", "(not set, defaults to 'system')"),
        "DEFAULT_USER_ADMIN": os.getenv("DEFAULT_USER_ADMIN", "(not set, defaults to 'true')"),
        "CREDENTIAL_MASTER_KEY": "***SET***" if os.getenv("CREDENTIAL_MASTER_KEY") else "(not set, using auto-generated)",
    }
    
    for key, value in env_vars.items():
        print(f"  {key}: {value}")
    
    # Summary
    print("\n" + "=" * 70)
    print("Summary")
    print("=" * 70)
    
    if is_initialized:
        print("✓ AuthContext is properly initialized")
        print("✓ System is ready for credential-based operations")
        print("\nIf you're still seeing errors in your production environment:")
        print("  1. Check that the server is starting with the same Python environment")
        print("  2. Verify that production_server.py is initializing AuthContext")
        print("  3. Check for module reloading or multiple Python processes")
        print("  4. Review server logs for '[AUTH] Initialized global auth context' message")
    else:
        print("✗ AuthContext needs to be initialized")
        print("\nIn your main application startup (main.py or production_server.py):")
        print("  from services.credentials import AuthContext")
        print("  AuthContext.initialize_from_env()")
    
    print()


if __name__ == "__main__":
    diagnose()
