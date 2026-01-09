"""
Secure credential management for skill-local database configurations.

Provides user-isolated credential storage with encryption.
"""

from .vault import CredentialVault, CredentialNotFoundError, UnauthorizedAccessError, get_vault
from .models import DatabaseCredential, CredentialReference, UserContext
from .defaults import get_system_user, get_default_user, create_user_context
from .auth_context import AuthContext, get_current_user

__all__ = [
    "CredentialVault",
    "DatabaseCredential", 
    "CredentialReference",
    "UserContext",
    "CredentialNotFoundError",
    "UnauthorizedAccessError",
    "get_vault",
    "get_system_user",
    "get_default_user",
    "create_user_context",
    "AuthContext",
    "get_current_user"
]
