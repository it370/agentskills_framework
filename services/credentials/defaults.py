"""
Default user contexts for credential management.

Use these when you don't have a full user authentication system yet.
"""

import os
from .models import UserContext


def get_system_user() -> UserContext:
    """
    Get a system-level user context for application-wide credentials.
    
    Use this for:
    - Development/testing
    - Single-user applications
    - System-level database connections
    
    Example:
        vault = get_vault()
        system_user = get_system_user()
        vault.store_credential(system_user, "main_db", ...)
    """
    return UserContext(
        user_id="system",
        username="system@app",
        roles=["admin"]
    )


def get_default_user() -> UserContext:
    """
    Get default user from environment or system user.
    
    Set DEFAULT_USER_ID environment variable to customize.
    
    Example:
        export DEFAULT_USER_ID="myapp_user"
        
        user = get_default_user()
        vault.store_credential(user, "my_db", ...)
    """
    user_id = os.getenv("DEFAULT_USER_ID", "system")
    return UserContext(
        user_id=user_id,
        username=f"{user_id}@app",
        roles=["admin"]
    )


def create_user_context(user_id: str, is_admin: bool = False) -> UserContext:
    """
    Helper to create a user context from just a user ID.
    
    Args:
        user_id: Unique user identifier
        is_admin: Whether user has admin privileges
    
    Returns:
        UserContext instance
    
    Example:
        user = create_user_context("alice")
        vault.store_credential(user, "alice_db", ...)
    """
    roles = ["admin", "user"] if is_admin else ["user"]
    return UserContext(
        user_id=user_id,
        username=f"{user_id}@app",
        roles=roles
    )
