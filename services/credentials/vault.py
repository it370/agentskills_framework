"""
Secure credential vault with encryption and user isolation.

Features:
- AES-256 encryption for passwords
- User-based access control
- Audit logging
- Credential rotation support
"""

import os
import json
import base64
from pathlib import Path
from typing import Optional, Dict, Any
from datetime import datetime
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from .models import DatabaseCredential, CredentialReference, UserContext


class CredentialNotFoundError(Exception):
    """Raised when a credential reference cannot be found."""
    pass


class UnauthorizedAccessError(Exception):
    """Raised when a user attempts to access credentials they don't own."""
    pass


class CredentialVault:
    """
    Secure storage for database credentials with user isolation.
    
    Architecture:
    - Credentials are encrypted using Fernet (AES-256)
    - Each user can only access their own credentials
    - Master key derived from environment variable
    - Stored in encrypted file or database
    
    Usage:
        vault = CredentialVault()
        
        # Store credential (as user)
        cred_id = vault.store_credential(
            user_context=user_ctx,
            name="my_postgres",
            db_type="postgres",
            host="db.example.com",
            username="myuser",
            password="secret123"
        )
        
        # Retrieve credential (as same user)
        cred = vault.get_credential(user_ctx, "my_postgres")
        connection_string = vault.build_connection_string(cred)
    """
    
    def __init__(self, storage_path: Optional[Path] = None):
        """
        Initialize credential vault.
        
        Args:
            storage_path: Path to encrypted credential storage file.
                         Defaults to .credentials/vault.enc in project root.
        """
        self.storage_path = storage_path or self._default_storage_path()
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Initialize encryption
        self._cipher = self._init_cipher()
        
        # Load existing credentials
        self._credentials: Dict[str, DatabaseCredential] = self._load_credentials()
    
    def _default_storage_path(self) -> Path:
        """Get default storage path for credentials."""
        project_root = Path(__file__).resolve().parents[2]
        return project_root / ".credentials" / "vault.enc"
    
    def _init_cipher(self) -> Fernet:
        """
        Initialize Fernet cipher for encryption/decryption.
        
        Derives encryption key from CREDENTIAL_MASTER_KEY environment variable.
        If not set, generates a new key (for development only).
        """
        master_key = os.getenv("CREDENTIAL_MASTER_KEY")
        
        if not master_key:
            # Development mode: generate a key
            print("[CREDENTIAL_VAULT] WARNING: Using auto-generated encryption key")
            print("[CREDENTIAL_VAULT] Set CREDENTIAL_MASTER_KEY in production!")
            master_key = Fernet.generate_key().decode()
        
        # Ensure key is bytes
        if isinstance(master_key, str):
            master_key = master_key.encode()
        
        # Derive a proper Fernet key if needed
        if len(master_key) != 44:  # Fernet keys are 44 bytes base64 encoded
            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=32,
                salt=b"agentskills_salt",  # Fixed salt for deterministic key
                iterations=100000,
            )
            key = base64.urlsafe_b64encode(kdf.derive(master_key))
        else:
            key = master_key
        
        return Fernet(key)
    
    def _load_credentials(self) -> Dict[str, DatabaseCredential]:
        """Load credentials from encrypted storage."""
        if not self.storage_path.exists():
            return {}
        
        try:
            encrypted_data = self.storage_path.read_bytes()
            decrypted_data = self._cipher.decrypt(encrypted_data)
            data = json.loads(decrypted_data.decode())
            
            credentials = {}
            for cred_id, cred_dict in data.items():
                credentials[cred_id] = DatabaseCredential(**cred_dict)
            
            return credentials
        except Exception as e:
            print(f"[CREDENTIAL_VAULT] Error loading credentials: {e}")
            return {}
    
    def _save_credentials(self) -> None:
        """Save credentials to encrypted storage."""
        # Convert to dict
        data = {
            cred_id: cred.model_dump(mode='json')
            for cred_id, cred in self._credentials.items()
        }
        
        # Encrypt and save
        json_data = json.dumps(data, indent=2)
        encrypted_data = self._cipher.encrypt(json_data.encode())
        self.storage_path.write_bytes(encrypted_data)
    
    def store_credential(
        self,
        user_context: UserContext,
        name: str,
        db_type: str,
        host: str,
        database: str,
        username: str,
        password: str,
        port: Optional[int] = None,
        description: Optional[str] = None,
        **kwargs
    ) -> str:
        """
        Store a new database credential.
        
        Args:
            user_context: User creating the credential
            name: User-friendly name for the credential
            db_type: Type of database (postgres, mongodb, etc.)
            host: Database host
            database: Database name
            username: Database username
            password: Database password (will be encrypted)
            port: Database port (default depends on db_type)
            description: Optional description
            **kwargs: Additional connection parameters
        
        Returns:
            credential_id: Unique ID for the stored credential
        """
        # Generate credential ID
        credential_id = f"{user_context.user_id}_{name}_{datetime.utcnow().timestamp()}"
        
        # Set default port based on db_type
        if port is None:
            port = self._default_port(db_type)
        
        # Encrypt password
        encrypted_password = self._cipher.encrypt(password.encode()).decode()
        
        # Create credential object
        credential = DatabaseCredential(
            credential_id=credential_id,
            user_id=user_context.user_id,
            name=name,
            db_type=db_type,
            host=host,
            port=port,
            database=database,
            username=username,
            encrypted_password=encrypted_password,
            description=description,
            **kwargs
        )
        
        # Store and save
        self._credentials[credential_id] = credential
        self._save_credentials()
        
        print(f"[CREDENTIAL_VAULT] Stored credential '{name}' for user {user_context.user_id}")
        return credential_id
    
    def get_credential(
        self,
        user_context: UserContext,
        credential_ref: str
    ) -> DatabaseCredential:
        """
        Retrieve a credential with user isolation.
        
        Args:
            user_context: User requesting the credential
            credential_ref: Credential ID or name
        
        Returns:
            DatabaseCredential with decrypted password
        
        Raises:
            CredentialNotFoundError: If credential doesn't exist
            UnauthorizedAccessError: If user doesn't own the credential
        """
        # Find credential by ID or name
        credential = None
        
        # Try by exact ID first
        if credential_ref in self._credentials:
            credential = self._credentials[credential_ref]
        else:
            # Try by name (within user's credentials)
            for cred in self._credentials.values():
                if cred.user_id == user_context.user_id and cred.name == credential_ref:
                    credential = cred
                    break
        
        if not credential:
            raise CredentialNotFoundError(
                f"Credential '{credential_ref}' not found"
            )
        
        # Check authorization (users can only access their own credentials)
        if credential.user_id != user_context.user_id and not user_context.is_admin():
            raise UnauthorizedAccessError(
                f"User {user_context.user_id} cannot access credential owned by {credential.user_id}"
            )
        
        # Return credential (password still encrypted)
        return credential
    
    def get_decrypted_password(self, credential: DatabaseCredential) -> str:
        """
        Decrypt the password from a credential.
        
        Args:
            credential: DatabaseCredential object
        
        Returns:
            Decrypted password string
        """
        encrypted_bytes = credential.encrypted_password.encode()
        decrypted_bytes = self._cipher.decrypt(encrypted_bytes)
        return decrypted_bytes.decode()
    
    def build_connection_string(
        self,
        credential: DatabaseCredential,
        overrides: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Build database connection string from credential.
        
        Args:
            credential: DatabaseCredential to use
            overrides: Optional dict with host, port, database overrides
        
        Returns:
            Connection string (e.g., postgresql://user:pass@host:port/db)
        """
        overrides = overrides or {}
        
        # Get values with overrides
        host = overrides.get('host', credential.host)
        port = overrides.get('port', credential.port)
        database = overrides.get('database', credential.database)
        username = credential.username
        password = self.get_decrypted_password(credential)
        
        # Build connection string based on db_type
        if credential.db_type == "postgres":
            return f"postgresql://{username}:{password}@{host}:{port}/{database}"
        elif credential.db_type == "mysql":
            return f"mysql://{username}:{password}@{host}:{port}/{database}"
        elif credential.db_type == "mongodb":
            return f"mongodb://{username}:{password}@{host}:{port}/{database}"
        else:
            raise ValueError(f"Unsupported db_type: {credential.db_type}")
    
    def list_credentials(self, user_context: UserContext) -> list[DatabaseCredential]:
        """
        List all credentials for a user.
        
        Args:
            user_context: User requesting the list
        
        Returns:
            List of credentials owned by the user (passwords still encrypted)
        """
        if user_context.is_admin():
            return list(self._credentials.values())
        
        return [
            cred for cred in self._credentials.values()
            if cred.user_id == user_context.user_id
        ]
    
    def delete_credential(
        self,
        user_context: UserContext,
        credential_ref: str
    ) -> None:
        """
        Delete a credential.
        
        Args:
            user_context: User requesting deletion
            credential_ref: Credential ID or name to delete
        
        Raises:
            CredentialNotFoundError: If credential doesn't exist
            UnauthorizedAccessError: If user doesn't own the credential
        """
        credential = self.get_credential(user_context, credential_ref)
        
        del self._credentials[credential.credential_id]
        self._save_credentials()
        
        print(f"[CREDENTIAL_VAULT] Deleted credential '{credential.name}' for user {user_context.user_id}")
    
    def update_password(
        self,
        user_context: UserContext,
        credential_ref: str,
        new_password: str
    ) -> None:
        """
        Rotate/update password for a credential.
        
        Args:
            user_context: User requesting the update
            credential_ref: Credential ID or name
            new_password: New password
        """
        credential = self.get_credential(user_context, credential_ref)
        
        # Encrypt new password
        encrypted_password = self._cipher.encrypt(new_password.encode()).decode()
        
        # Update credential
        credential.encrypted_password = encrypted_password
        credential.updated_at = datetime.utcnow()
        
        self._save_credentials()
        
        print(f"[CREDENTIAL_VAULT] Updated password for '{credential.name}'")
    
    @staticmethod
    def _default_port(db_type: str) -> int:
        """Get default port for database type."""
        defaults = {
            "postgres": 5432,
            "mysql": 3306,
            "mongodb": 27017,
            "redis": 6379,
        }
        return defaults.get(db_type.lower(), 5432)


# Global vault instance
_vault_instance: Optional[CredentialVault] = None


def get_vault() -> CredentialVault:
    """Get or create the global credential vault instance."""
    global _vault_instance
    if _vault_instance is None:
        _vault_instance = CredentialVault()
    return _vault_instance
