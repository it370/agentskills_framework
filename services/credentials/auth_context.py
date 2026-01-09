"""
Global authentication context for the application.

Provides a singleton auth context that can be initialized once at startup
and accessed throughout the application.
"""

import os
from typing import Optional
from .models import UserContext


class AuthContext:
    """
    Global authentication context singleton.
    
    Initialize once at application startup, then access anywhere.
    
    Usage:
        # In main.py or startup
        from services.credentials import AuthContext, get_system_user
        
        auth = AuthContext.initialize(get_system_user())
        
        # Anywhere in your app
        from services.credentials import AuthContext
        
        user = AuthContext.get_current_user()
    """
    
    _instance: Optional['AuthContext'] = None
    _current_user: Optional[UserContext] = None
    
    def __init__(self):
        """Private constructor. Use initialize() or get_instance() instead."""
        pass
    
    @classmethod
    def initialize(cls, user_context: UserContext) -> 'AuthContext':
        """
        Initialize the global auth context.
        
        Call this once at application startup.
        
        Args:
            user_context: The user context to use globally
        
        Returns:
            AuthContext instance
        
        Example:
            from services.credentials import AuthContext, get_system_user
            
            # At startup
            auth = AuthContext.initialize(get_system_user())
            print(f"Initialized auth for user: {auth.get_current_user().user_id}")
        """
        if cls._instance is None:
            cls._instance = cls()
        
        cls._current_user = user_context
        return cls._instance
    
    @classmethod
    def initialize_from_env(cls) -> 'AuthContext':
        """
        Initialize from environment variables.
        
        Reads DEFAULT_USER_ID from environment, defaults to "system".
        
        Example:
            # Set in environment
            export DEFAULT_USER_ID="myapp"
            
            # In code
            auth = AuthContext.initialize_from_env()
        """
        user_id = os.getenv("DEFAULT_USER_ID", "system")
        is_admin = os.getenv("DEFAULT_USER_ADMIN", "true").lower() in ("true", "1", "yes")
        
        roles = ["admin", "user"] if is_admin else ["user"]
        user_context = UserContext(
            user_id=user_id,
            username=f"{user_id}@app",
            roles=roles
        )
        
        return cls.initialize(user_context)
    
    @classmethod
    def get_instance(cls) -> 'AuthContext':
        """
        Get the auth context instance.
        
        Raises:
            RuntimeError: If not initialized
        
        Returns:
            AuthContext instance
        """
        if cls._instance is None:
            raise RuntimeError(
                "AuthContext not initialized. Call AuthContext.initialize() first."
            )
        return cls._instance
    
    @classmethod
    def get_current_user(cls) -> UserContext:
        """
        Get the current user context.
        
        This is the main method used throughout the application.
        
        Returns:
            Current UserContext
        
        Raises:
            RuntimeError: If not initialized
        
        Example:
            from services.credentials import AuthContext
            
            user = AuthContext.get_current_user()
            # Use user for credential access, skill execution, etc.
        """
        if cls._current_user is None:
            raise RuntimeError(
                "AuthContext not initialized. Call AuthContext.initialize() first.\n"
                "\n"
                "Example:\n"
                "  from services.credentials import AuthContext, get_system_user\n"
                "  AuthContext.initialize(get_system_user())"
            )
        return cls._current_user
    
    @classmethod
    def set_current_user(cls, user_context: UserContext) -> None:
        """
        Update the current user context.
        
        Useful for switching users or testing.
        
        Args:
            user_context: New user context
        """
        cls._current_user = user_context
    
    @classmethod
    def is_initialized(cls) -> bool:
        """Check if auth context has been initialized."""
        return cls._current_user is not None
    
    @classmethod
    def reset(cls) -> None:
        """
        Reset the auth context.
        
        Useful for testing. Not recommended in production.
        """
        cls._instance = None
        cls._current_user = None


# Convenience function for quick access
def get_current_user() -> UserContext:
    """
    Get the current user context from global auth.
    
    This is a convenience function that's easier to import.
    
    Returns:
        Current UserContext
    
    Example:
        from services.credentials import get_current_user
        
        user = get_current_user()
    """
    return AuthContext.get_current_user()
