"""
User management service for authentication and authorization.

Features:
- User registration with email and password
- Login with JWT token generation
- Password hashing with bcrypt
- Password reset via email
- User session tracking
"""

import os
import secrets
import hashlib
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
import psycopg
import asyncio
from pydantic import BaseModel, EmailStr, Field, validator
import jwt
import bcrypt


class UserRegistration(BaseModel):
    """User registration request"""
    username: str = Field(..., min_length=3, max_length=255)
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=255)
    
    @validator('username')
    def username_alphanumeric(cls, v):
        if not v.replace('_', '').replace('-', '').isalnum():
            raise ValueError('Username must be alphanumeric (with optional _ or -)')
        return v
    
    @validator('password')
    def password_strong(cls, v):
        if len(v) < 8:
            raise ValueError('Password must be at least 8 characters')
        if not any(c.isupper() for c in v):
            raise ValueError('Password must contain at least one uppercase letter')
        if not any(c.islower() for c in v):
            raise ValueError('Password must contain at least one lowercase letter')
        if not any(c.isdigit() for c in v):
            raise ValueError('Password must contain at least one digit')
        return v


class UserLogin(BaseModel):
    """User login request"""
    username: str
    password: str


class PasswordResetRequest(BaseModel):
    """Password reset request"""
    email: EmailStr


class PasswordReset(BaseModel):
    """Password reset with token"""
    token: str
    new_password: str = Field(..., min_length=8, max_length=255)
    
    @validator('new_password')
    def password_strong(cls, v):
        if len(v) < 8:
            raise ValueError('Password must be at least 8 characters')
        if not any(c.isupper() for c in v):
            raise ValueError('Password must contain at least one uppercase letter')
        if not any(c.islower() for c in v):
            raise ValueError('Password must contain at least one lowercase letter')
        if not any(c.isdigit() for c in v):
            raise ValueError('Password must contain at least one digit')
        return v


class User(BaseModel):
    """User model"""
    id: int
    username: str
    email: str
    is_active: bool
    is_admin: bool
    created_at: datetime
    last_login_at: Optional[datetime] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "username": self.username,
            "email": self.email,
            "is_active": self.is_active,
            "is_admin": self.is_admin,
            "created_at": self.created_at.isoformat(),
            "last_login_at": self.last_login_at.isoformat() if self.last_login_at else None
        }


class UserService:
    """Service for user management operations"""
    
    def __init__(self, db_uri: str, jwt_secret: str, jwt_expiry_hours: int = 24):
        self.db_uri = db_uri
        self.jwt_secret = jwt_secret
        self.jwt_expiry_hours = jwt_expiry_hours
        self.jwt_algorithm = "HS256"
    
    def _hash_password(self, password: str) -> str:
        """Hash password using bcrypt"""
        salt = bcrypt.gensalt()
        hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
        return hashed.decode('utf-8')
    
    def _verify_password(self, password: str, password_hash: str) -> bool:
        """Verify password against hash"""
        return bcrypt.checkpw(password.encode('utf-8'), password_hash.encode('utf-8'))
    
    def _generate_jwt(self, user_id: int, username: str, is_admin: bool) -> tuple[str, str]:
        """
        Generate JWT token for user
        
        Returns:
            tuple of (token, jti)
        """
        jti = secrets.token_urlsafe(32)
        now = datetime.utcnow()
        expiry = now + timedelta(hours=self.jwt_expiry_hours)
        
        payload = {
            "jti": jti,
            "user_id": user_id,
            "username": username,
            "is_admin": is_admin,
            "iat": now,
            "exp": expiry
        }
        
        token = jwt.encode(payload, self.jwt_secret, algorithm=self.jwt_algorithm)
        return token, jti
    
    def verify_jwt(self, token: str) -> Optional[Dict[str, Any]]:
        """
        Verify JWT token and return payload
        
        Returns:
            Payload dict if valid, None if invalid
        """
        try:
            payload = jwt.decode(token, self.jwt_secret, algorithms=[self.jwt_algorithm])
            return payload
        except jwt.ExpiredSignatureError:
            return None
        except jwt.InvalidTokenError:
            return None
    
    async def register_user(self, registration: UserRegistration) -> User:
        """
        Register a new user
        
        Raises:
            ValueError: If username or email already exists
        """
        def _register_sync():
            with psycopg.connect(self.db_uri, autocommit=True) as conn:
                with conn.cursor() as cur:
                    # Check if username exists
                    cur.execute("SELECT id FROM users WHERE username = %s", (registration.username,))
                    if cur.fetchone():
                        raise ValueError(f"Username '{registration.username}' already exists")
                    
                    # Check if email exists
                    cur.execute("SELECT id FROM users WHERE email = %s", (registration.email,))
                    if cur.fetchone():
                        raise ValueError(f"Email '{registration.email}' already exists")
                    
                    # Hash password
                    password_hash = self._hash_password(registration.password)
                    
                    # Insert user
                    cur.execute("""
                        INSERT INTO users (username, email, password_hash, is_active, is_admin)
                        VALUES (%s, %s, %s, %s, %s)
                        RETURNING id, username, email, is_active, is_admin, created_at, last_login_at
                    """, (registration.username, registration.email, password_hash, True, False))
                    
                    row = cur.fetchone()
                    return User(
                        id=row[0],
                        username=row[1],
                        email=row[2],
                        is_active=row[3],
                        is_admin=row[4],
                        created_at=row[5],
                        last_login_at=row[6]
                    )
        
        return await asyncio.to_thread(_register_sync)
    
    async def login(self, login: UserLogin, ip_address: Optional[str] = None, user_agent: Optional[str] = None) -> tuple[str, User]:
        """
        Authenticate user and generate JWT token
        
        Returns:
            tuple of (token, user)
        
        Raises:
            ValueError: If credentials are invalid
        """
        def _login_sync():
            with psycopg.connect(self.db_uri, autocommit=True) as conn:
                with conn.cursor() as cur:
                    # Get user by username
                    cur.execute("""
                        SELECT id, username, email, password_hash, is_active, is_admin, created_at, last_login_at
                        FROM users
                        WHERE username = %s
                    """, (login.username,))
                    
                    row = cur.fetchone()
                    if not row:
                        raise ValueError("Invalid username or password")
                    
                    user_id, username, email, password_hash, is_active, is_admin, created_at, last_login_at = row
                    
                    # Check if user is active
                    if not is_active:
                        raise ValueError("User account is disabled")
                    
                    # Verify password
                    if not self._verify_password(login.password, password_hash):
                        raise ValueError("Invalid username or password")
                    
                    # Generate JWT token
                    token, jti = self._generate_jwt(user_id, username, is_admin)
                    
                    # Update last login time
                    cur.execute("""
                        UPDATE users
                        SET last_login_at = NOW()
                        WHERE id = %s
                    """, (user_id,))
                    
                    # Store session
                    expiry = datetime.utcnow() + timedelta(hours=self.jwt_expiry_hours)
                    cur.execute("""
                        INSERT INTO user_sessions (user_id, token_jti, expires_at, ip_address, user_agent)
                        VALUES (%s, %s, %s, %s, %s)
                    """, (user_id, jti, expiry, ip_address, user_agent))
                    
                    user = User(
                        id=user_id,
                        username=username,
                        email=email,
                        is_active=is_active,
                        is_admin=is_admin,
                        created_at=created_at,
                        last_login_at=datetime.utcnow()
                    )
                    
                    return token, user
        
        return await asyncio.to_thread(_login_sync)
    
    async def verify_session(self, token: str) -> Optional[User]:
        """
        Verify JWT token and return user if valid
        
        Returns:
            User if token is valid, None otherwise
        """
        payload = self.verify_jwt(token)
        if not payload:
            return None
        
        def _verify_sync():
            with psycopg.connect(self.db_uri) as conn:
                with conn.cursor() as cur:
                    # Check if session exists and is not expired
                    cur.execute("""
                        SELECT s.id, u.id, u.username, u.email, u.is_active, u.is_admin, u.created_at, u.last_login_at
                        FROM user_sessions s
                        JOIN users u ON s.user_id = u.id
                        WHERE s.token_jti = %s AND s.expires_at > NOW() AND u.is_active = TRUE
                    """, (payload.get("jti"),))
                    
                    row = cur.fetchone()
                    if not row:
                        return None
                    
                    # Update last used time
                    with psycopg.connect(self.db_uri, autocommit=True) as update_conn:
                        with update_conn.cursor() as update_cur:
                            update_cur.execute("""
                                UPDATE user_sessions
                                SET last_used_at = NOW()
                                WHERE id = %s
                            """, (row[0],))
                    
                    return User(
                        id=row[1],
                        username=row[2],
                        email=row[3],
                        is_active=row[4],
                        is_admin=row[5],
                        created_at=row[6],
                        last_login_at=row[7]
                    )
        
        return await asyncio.to_thread(_verify_sync)
    
    async def logout(self, token: str) -> bool:
        """
        Logout user by invalidating JWT token (remove from sessions)
        
        Returns:
            True if logout successful, False otherwise
        """
        payload = self.verify_jwt(token)
        if not payload:
            return False
        
        def _logout_sync():
            with psycopg.connect(self.db_uri, autocommit=True) as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        DELETE FROM user_sessions
                        WHERE token_jti = %s
                    """, (payload.get("jti"),))
                    return cur.rowcount > 0
        
        return await asyncio.to_thread(_logout_sync)
    
    async def request_password_reset(self, email: str) -> str:
        """
        Generate password reset token for user
        
        Returns:
            Reset token to be sent via email
        
        Raises:
            ValueError: If email not found
        """
        def _request_sync():
            with psycopg.connect(self.db_uri, autocommit=True) as conn:
                with conn.cursor() as cur:
                    # Get user by email
                    cur.execute("SELECT id FROM users WHERE email = %s AND is_active = TRUE", (email,))
                    row = cur.fetchone()
                    if not row:
                        raise ValueError("Email not found")
                    
                    user_id = row[0]
                    
                    # Generate token
                    token = secrets.token_urlsafe(32)
                    expiry = datetime.utcnow() + timedelta(hours=1)  # 1 hour expiry
                    
                    # Store token
                    cur.execute("""
                        INSERT INTO password_reset_tokens (user_id, token, expires_at)
                        VALUES (%s, %s, %s)
                    """, (user_id, token, expiry))
                    
                    return token
        
        return await asyncio.to_thread(_request_sync)
    
    async def reset_password(self, reset: PasswordReset) -> bool:
        """
        Reset user password using token
        
        Returns:
            True if reset successful
        
        Raises:
            ValueError: If token is invalid or expired
        """
        def _reset_sync():
            with psycopg.connect(self.db_uri, autocommit=True) as conn:
                with conn.cursor() as cur:
                    # Get token
                    cur.execute("""
                        SELECT user_id, expires_at, used
                        FROM password_reset_tokens
                        WHERE token = %s
                    """, (reset.token,))
                    
                    row = cur.fetchone()
                    if not row:
                        raise ValueError("Invalid reset token")
                    
                    user_id, expires_at, used = row
                    
                    if used:
                        raise ValueError("Reset token has already been used")
                    
                    if expires_at < datetime.utcnow():
                        raise ValueError("Reset token has expired")
                    
                    # Hash new password
                    password_hash = self._hash_password(reset.new_password)
                    
                    # Update password
                    cur.execute("""
                        UPDATE users
                        SET password_hash = %s, updated_at = NOW()
                        WHERE id = %s
                    """, (password_hash, user_id))
                    
                    # Mark token as used
                    cur.execute("""
                        UPDATE password_reset_tokens
                        SET used = TRUE
                        WHERE token = %s
                    """, (reset.token,))
                    
                    # Invalidate all user sessions (force re-login)
                    cur.execute("""
                        DELETE FROM user_sessions
                        WHERE user_id = %s
                    """, (user_id,))
                    
                    return True
        
        return await asyncio.to_thread(_reset_sync)
    
    async def get_user_by_id(self, user_id: int) -> Optional[User]:
        """Get user by ID"""
        def _get_sync():
            with psycopg.connect(self.db_uri) as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT id, username, email, is_active, is_admin, created_at, last_login_at
                        FROM users
                        WHERE id = %s
                    """, (user_id,))
                    
                    row = cur.fetchone()
                    if not row:
                        return None
                    
                    return User(
                        id=row[0],
                        username=row[1],
                        email=row[2],
                        is_active=row[3],
                        is_admin=row[4],
                        created_at=row[5],
                        last_login_at=row[6]
                    )
        
        return await asyncio.to_thread(_get_sync)
    
    async def get_user_by_username(self, username: str) -> User:
        """
        Get user by username
        
        Returns:
            User object
            
        Raises:
            HTTPException: If user not found (404)
        """
        from fastapi import HTTPException, status
        
        def _get_user_sync():
            with psycopg.connect(self.db_uri) as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT id, username, email, is_active, is_admin, created_at, last_login_at
                        FROM users
                        WHERE username = %s
                    """, (username,))
                    
                    row = cur.fetchone()
                    if not row:
                        return None
                    
                    return User(
                        id=row[0],
                        username=row[1],
                        email=row[2],
                        is_active=row[3],
                        is_admin=row[4],
                        created_at=row[5],
                        last_login_at=row[6]
                    )
        
        user = await asyncio.to_thread(_get_user_sync)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"User '{username}' not found"
            )
        return user
    
    async def cleanup_expired_sessions(self):
        """Cleanup expired sessions and reset tokens"""
        def _cleanup_sync():
            with psycopg.connect(self.db_uri, autocommit=True) as conn:
                with conn.cursor() as cur:
                    # Delete expired sessions
                    cur.execute("DELETE FROM user_sessions WHERE expires_at < NOW()")
                    sessions_deleted = cur.rowcount
                    
                    # Delete expired reset tokens
                    cur.execute("DELETE FROM password_reset_tokens WHERE expires_at < NOW()")
                    tokens_deleted = cur.rowcount
                    
                    return sessions_deleted, tokens_deleted
        
        return await asyncio.to_thread(_cleanup_sync)


# Global user service instance
_user_service: Optional[UserService] = None


def get_user_service() -> UserService:
    """Get global user service instance"""
    global _user_service
    if _user_service is None:
        db_uri = os.getenv("DATABASE_URL")
        if not db_uri:
            raise RuntimeError("DATABASE_URL not set")
        
        jwt_secret = os.getenv("JWT_SECRET")
        if not jwt_secret:
            raise RuntimeError("JWT_SECRET not set")
        
        jwt_expiry_hours = int(os.getenv("JWT_EXPIRY_HOURS", "24"))
        
        _user_service = UserService(db_uri, jwt_secret, jwt_expiry_hours)
    
    return _user_service
