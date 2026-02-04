"""
Authentication API endpoints.

Provides:
- User registration
- Login
- Logout
- Password reset request
- Password reset
- User profile
"""

import os
from typing import Optional
from fastapi import APIRouter, HTTPException, status, Request
from pydantic import BaseModel

from services.user_service import (
    get_user_service,
    UserRegistration,
    UserLogin,
    PasswordResetRequest,
    PasswordReset,
    User
)
from services.email_service import get_email_service
from services.auth_middleware import (
    AuthenticatedUser,
    OptionalUser,
    get_current_user
)
from services.workspace_service import get_workspace_service


router = APIRouter(prefix="/auth", tags=["Authentication"])


class TokenResponse(BaseModel):
    """Login response with token"""
    access_token: str
    token_type: str = "bearer"
    user: dict


class MessageResponse(BaseModel):
    """Generic message response"""
    message: str


class SystemSetupResponse(BaseModel):
    """System setup response"""
    message: str
    system_exists: bool


@router.post("/setup/check", response_model=SystemSetupResponse)
async def check_system_setup():
    """Check if system user exists"""
    user_service = get_user_service()
    
    try:
        await user_service.get_user_by_username("system")
        return SystemSetupResponse(
            message="System user already exists",
            system_exists=True
        )
    except HTTPException:
        return SystemSetupResponse(
            message="System user not found - setup required",
            system_exists=False
        )


@router.post("/setup/reset-request", response_model=MessageResponse)
async def request_system_password_reset(reset_request: PasswordResetRequest):
    """Request password reset for system user (only if email matches)"""
    user_service = get_user_service()
    email_service = get_email_service()
    
    if not email_service:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Email service not configured. Please contact administrator."
        )
    
    # Get system user
    try:
        system_user = await user_service.get_user_by_username("system")
    except HTTPException:
        # Don't reveal if user exists or not for security
        return MessageResponse(
            message="If the email matches the system account, a password reset link will be sent."
        )
    
    # Check if email matches
    if system_user.email != reset_request.email:
        # Don't reveal that email doesn't match
        return MessageResponse(
            message="If the email matches the system account, a password reset link will be sent."
        )
    
    # Email matches, proceed with password reset
    reset_token = await user_service.create_password_reset_token(reset_request.email)
    
    if reset_token:
        # Construct reset URL
        reset_url_base = os.getenv("UI_APP_URL", "http://localhost:3000") + "/reset-password"
        reset_url = f"{reset_url_base}?token={reset_token}"
        
        try:
            await email_service.send_password_reset_email(
                to_email=reset_request.email,
                reset_url=reset_url,
                username=system_user.username
            )
        except Exception as e:
            print(f"[AUTH] Failed to send password reset email: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to send password reset email. Please check email configuration."
            )
    
    return MessageResponse(
        message="If the email matches the system account, a password reset link will be sent."
    )


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(registration: UserRegistration):
    """
    Register a new user
    
    - **username**: Unique username (3-255 chars, alphanumeric with _ or -)
    - **email**: Valid email address
    - **password**: Strong password (min 8 chars, must contain uppercase, lowercase, digit)
    """
    user_service = get_user_service()
    
    try:
        user = await user_service.register_user(registration)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    
    # Auto-login after registration
    token, user = await user_service.login(
        UserLogin(username=registration.username, password=registration.password)
    )
    
    # Send welcome email (optional, don't fail if SMTP not configured)
    email_service = get_email_service()
    if email_service:
        try:
            login_url = os.getenv("UI_APP_URL", "http://localhost:3000") + "/login"
            await email_service.send_welcome_email(
                user.email,
                user.username,
                login_url
            )
        except Exception as e:
            # Log error but don't fail registration
            print(f"[AUTH] Failed to send welcome email: {e}")
    
    workspace_service = get_workspace_service()
    default_workspace = await workspace_service.ensure_default(user.id)
    user_payload = user.to_dict()
    user_payload["default_workspace_id"] = default_workspace.id

    return TokenResponse(
        access_token=token,
        token_type="bearer",
        user=user_payload
    )


@router.post("/login", response_model=TokenResponse)
async def login(login_data: UserLogin, request: Request):
    """
    Login with username and password
    
    Returns JWT token for authentication
    """
    user_service = get_user_service()
    
    # Get IP address and user agent
    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("User-Agent")
    
    try:
        token, user = await user_service.login(login_data, ip_address, user_agent)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    workspace_service = get_workspace_service()
    default_workspace = await workspace_service.ensure_default(user.id)
    user_payload = user.to_dict()
    user_payload["default_workspace_id"] = default_workspace.id

    return TokenResponse(
        access_token=token,
        token_type="bearer",
        user=user_payload
    )


@router.post("/logout", response_model=MessageResponse)
async def logout(current_user: AuthenticatedUser, request: Request):
    """
    Logout current user (invalidate token)
    """
    user_service = get_user_service()
    
    # Extract token from Authorization header
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authorization header"
        )
    
    token = auth_header[7:]
    await user_service.logout(token)
    
    return MessageResponse(message="Logged out successfully")


@router.get("/me", response_model=dict)
async def get_profile(current_user: AuthenticatedUser):
    """
    Get current user profile
    """
    workspace_service = get_workspace_service()
    default_workspace = await workspace_service.ensure_default(current_user.id)
    user_payload = current_user.to_dict()
    user_payload["default_workspace_id"] = default_workspace.id
    return user_payload


@router.post("/password-reset-request", response_model=MessageResponse)
async def request_password_reset(reset_request: PasswordResetRequest):
    """
    Request password reset
    
    Sends reset link to user's email
    """
    user_service = get_user_service()
    email_service = get_email_service()
    
    if not email_service:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Email service not configured. Please contact administrator."
        )
    
    try:
        token = await user_service.request_password_reset(reset_request.email)
    except ValueError as e:
        # Return success even if email not found (security best practice)
        return MessageResponse(
            message="If the email exists, a password reset link has been sent."
        )
    
    # Send reset email
    try:
        reset_url_base = os.getenv("UI_APP_URL", "http://localhost:3000") + "/reset-password"
        
        # Get username for email
        # We need to query the user again (inefficient but secure)
        def _get_username_sync():
            import psycopg
            db_uri = os.getenv("DATABASE_URL")
            with psycopg.connect(db_uri) as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT username FROM users WHERE email = %s",
                        (reset_request.email,)
                    )
                    row = cur.fetchone()
                    return row[0] if row else None
        
        import asyncio
        username = await asyncio.to_thread(_get_username_sync)
        
        if username:
            await email_service.send_password_reset_email(
                reset_request.email,
                username,
                token,
                reset_url_base
            )
    except Exception as e:
        # Log error but don't fail
        print(f"[AUTH] Failed to send password reset email: {e}")
    
    return MessageResponse(
        message="If the email exists, a password reset link has been sent."
    )


@router.post("/password-reset", response_model=MessageResponse)
async def reset_password(reset: PasswordReset):
    """
    Reset password using token
    
    - **token**: Reset token from email
    - **new_password**: New password (same requirements as registration)
    """
    user_service = get_user_service()
    
    try:
        await user_service.reset_password(reset)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    
    return MessageResponse(message="Password reset successfully. Please log in with your new password.")


@router.post("/verify-token")
async def verify_token(current_user: OptionalUser):
    """
    Verify if current token is valid
    
    Returns user info if valid, 401 if invalid
    """
    if not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    workspace_service = get_workspace_service()
    default_workspace = await workspace_service.ensure_default(current_user.id)
    user_payload = current_user.to_dict()
    user_payload["default_workspace_id"] = default_workspace.id
    return user_payload
