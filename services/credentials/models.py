"""
Data models for credential management.
"""

from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class DatabaseCredential(BaseModel):
    """
    Database credential stored in the vault.
    
    Passwords are encrypted at rest and only decrypted when accessed
    by the owning user.
    """
    credential_id: str = Field(description="Unique identifier for this credential")
    user_id: str = Field(description="Owner of this credential")
    name: str = Field(description="User-friendly name (e.g., 'my_postgres_db')")
    
    # Database connection details
    db_type: str = Field(description="Database type: postgres, mongodb, mysql, etc.")
    host: str
    port: int
    database: str
    username: str
    
    # Encrypted password (never stored in plain text)
    encrypted_password: str = Field(description="Encrypted password")
    
    # Metadata
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    description: Optional[str] = Field(default=None, description="Optional description")
    
    # Additional connection parameters (optional)
    ssl_mode: Optional[str] = None
    connection_timeout: Optional[int] = 30
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class CredentialReference(BaseModel):
    """
    Reference to a credential stored in the vault.
    
    This is what skills store in their db_config.json - just a reference,
    not the actual credentials.
    """
    credential_ref: str = Field(
        description="Name or ID of the credential in the vault"
    )
    
    # Optional overrides (can override host/database but not credentials)
    host: Optional[str] = None
    port: Optional[int] = None
    database: Optional[str] = None
    
    # Additional connection parameters
    timeout: Optional[float] = None
    ssl_mode: Optional[str] = None


class UserContext(BaseModel):
    """
    User context for credential access control.
    
    Passed during skill execution to ensure users can only access
    their own credentials.
    """
    user_id: str = Field(description="Authenticated user ID")
    username: str = Field(description="Username for logging")
    roles: list[str] = Field(default_factory=list, description="User roles")
    
    def is_admin(self) -> bool:
        """Check if user has admin privileges."""
        return "admin" in self.roles or "superuser" in self.roles
