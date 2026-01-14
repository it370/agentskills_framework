"""
Authentication middleware for FastAPI.

Provides:
- JWT token validation
- User authentication dependency
- Admin-only route protection
- Current user context injection
"""

from typing import Optional, Annotated
from fastapi import Depends, HTTPException, status, Header
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from .user_service import get_user_service, User


security = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: Annotated[Optional[HTTPAuthorizationCredentials], Depends(security)] = None,
    authorization: Optional[str] = Header(None)
) -> Optional[User]:
    """
    Get current authenticated user from JWT token
    
    Returns None if no token or invalid token
    """
    # Try Bearer token from security scheme first
    token = None
    if credentials:
        token = credentials.credentials
    # Fallback to Authorization header
    elif authorization and authorization.startswith("Bearer "):
        token = authorization[7:]
    
    if not token:
        return None
    
    user_service = get_user_service()
    user = await user_service.verify_session(token)
    return user


async def require_auth(
    current_user: Annotated[Optional[User], Depends(get_current_user)]
) -> User:
    """
    Require authentication - raises 401 if not authenticated
    
    Use this as a dependency for protected routes
    """
    if not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return current_user


async def require_admin(
    current_user: Annotated[User, Depends(require_auth)]
) -> User:
    """
    Require admin privileges - raises 403 if not admin
    
    Use this as a dependency for admin-only routes
    """
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required"
        )
    return current_user


# Optional authentication - doesn't raise error if not authenticated
OptionalUser = Annotated[Optional[User], Depends(get_current_user)]

# Required authentication - raises 401 if not authenticated
AuthenticatedUser = Annotated[User, Depends(require_auth)]

# Required admin - raises 403 if not admin
AdminUser = Annotated[User, Depends(require_admin)]
