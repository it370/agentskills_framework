# Secure Credentials System

Enterprise-grade credential management for skill-local database configurations in multi-user environments.

## Features

- 🔐 **AES-256 Encryption** - All passwords encrypted at rest
- 👥 **User Isolation** - Each user has their own credential namespace
- 🔄 **Password Rotation** - Update credentials without changing skills
- 📝 **Audit Trail** - Track credential creation and access
- 🏢 **Multi-tenant Safe** - Perfect for multi-user applications
- 📦 **Portable Skills** - Share skills without exposing secrets

## Quick Start

### 1. Install Dependencies

```bash
conda activate clearstar
pip install cryptography
```

### 2. Set Master Encryption Key

```bash
# Generate a secure key
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

# Set in environment
export CREDENTIAL_MASTER_KEY="your-generated-key-here"
```

### 3. Store a Credential

```bash
python -m scripts.credential_manager add \
  --user alice \
  --name my_postgres_db \
  --db-type postgres \
  --host db.example.com \
  --database production \
  --username dbuser
# Will prompt for password securely
```

### 4. Use in Skill

Simply reference the credential in your `skill.md`:

```yaml
---
name: MySkill
executor: action
action:
  type: data_query
  source: postgres
  query: "SELECT * FROM users WHERE id = {user_id}"
  credential_ref: "my_postgres_db"  # That's it!
---
```

### 5. Execute Skill

```python
from services.credentials import UserContext

result = await execute_skill(
    skill_name="MySkill",
    inputs={
        "user_id": 123,
        "user_context": UserContext(
            user_id="alice",
            username="alice@example.com",
            roles=["user"]
        )
    }
)
```

## CLI Tool Usage

### Add Credential
```bash
python -m scripts.credential_manager add --user alice --name prod_db
```

### List Credentials
```bash
python -m scripts.credential_manager list --user alice
```

### Update Password
```bash
python -m scripts.credential_manager update --user alice --name prod_db
```

### Delete Credential
```bash
python -m scripts.credential_manager delete --user alice --name prod_db
```

### Test Credential
```bash
python -m scripts.credential_manager test --user alice --name prod_db
```

## Python API

### Store Credential

```python
from services.credentials import get_vault, UserContext

vault = get_vault()
user = UserContext(user_id="alice", username="alice", roles=["user"])

cred_id = vault.store_credential(
    user_context=user,
    name="my_db",
    db_type="postgres",
    host="db.example.com",
    port=5432,
    database="mydb",
    username="dbuser",
    password="secret123",
    description="Production database"
)
```

### Retrieve Credential

```python
credential = vault.get_credential(user, "my_db")
connection_string = vault.build_connection_string(credential)
```

### List User's Credentials

```python
credentials = vault.list_credentials(user)
for cred in credentials:
    print(f"{cred.name}: {cred.host}:{cred.port}/{cred.database}")
```

### Update Password

```python
vault.update_password(user, "my_db", "new_password")
```

### Delete Credential

```python
vault.delete_credential(user, "my_db")
```

## Security Model

### Encryption
- Passwords encrypted using **Fernet (AES-256-CBC)**
- Master key derived from `CREDENTIAL_MASTER_KEY` environment variable
- Encrypted vault stored in `.credentials/vault.enc`

### User Isolation
- Each credential has an `owner` (user_id)
- Users can only access their own credentials
- Admin role can access all credentials

### Authorization Flow
```
User → Request Credential → Vault checks ownership → Decrypt → Return
                                    ↓
                              If not owner → 401 Unauthorized
```

### Best Practices

1. **Never commit passwords** - Use credential references
2. **Rotate regularly** - Update passwords periodically
3. **Use SSL/TLS** - Always encrypt database connections
4. **Backup vault** - `.credentials/vault.enc` is safe to backup (encrypted)
5. **Secure master key** - Store in secret manager (AWS Secrets, Vault, etc.)

## Architecture

```
┌────────────────────────────────────────┐
│  Skill (skill.md)                      │
│  ┌──────────────────────────────────┐  │
│  │ action:                          │  │
│  │   type: data_query               │  │
│  │   source: postgres               │  │
│  │   db_config_file: db_config.json │  │
│  └──────────────────────────────────┘  │
└────────────────────────────────────────┘
                ↓
┌────────────────────────────────────────┐
│  db_config.json                        │
│  ┌──────────────────────────────────┐  │
│  │ {                                │  │
│  │   "credential_ref": "my_db"      │  │
│  │ }                                │  │
│  └──────────────────────────────────┘  │
└────────────────────────────────────────┘
                ↓
┌────────────────────────────────────────┐
│  Credential Vault                      │
│  (.credentials/vault.enc)              │
│  ┌──────────────────────────────────┐  │
│  │ [AES-256 Encrypted]              │  │
│  │                                  │  │
│  │ userA_my_db:                     │  │
│  │   host: db.example.com           │  │
│  │   password: [encrypted]          │  │
│  │   owner: userA                   │  │
│  └──────────────────────────────────┘  │
└────────────────────────────────────────┘
                ↓
┌────────────────────────────────────────┐
│  Runtime (in-memory only)              │
│  postgresql://user:pass@host/db        │
└────────────────────────────────────────┘
```

## Migration from Global Config

### Before (Insecure)
```yaml
# Uses global DATABASE_URL from .env
action:
  type: data_query
  source: postgres
  query: "SELECT * FROM users"
```

### After (Secure)
```yaml
# Uses user-specific encrypted credential
action:
  type: data_query
  source: postgres
  query: "SELECT * FROM users"
  db_config_file: "db_config.json"
```

```json
// db_config.json
{
  "credential_ref": "my_secure_db"
}
```

## Examples

See:
- `scripts/demo_secure_credentials.py` - Complete walkthrough
- `scripts/credential_manager.py` - CLI tool
- `skills/DatabaseUserFetcher/` - Example skill
- `documentations/SECURE_CREDENTIALS.md` - Full documentation

## Troubleshooting

### "Credential not found"
```bash
# List available credentials
python -m scripts.credential_manager list --user <your_user>
```

### "Unauthorized access"
Make sure you're using the correct user_context - credentials are user-specific.

### "Decryption failed"
The `CREDENTIAL_MASTER_KEY` may have changed. Restore the original key or recreate credentials.

## Environment Variables

- `CREDENTIAL_MASTER_KEY` - Master encryption key (required in production)
- `DATABASE_URL` - Fallback if db_config_file not specified

## Files

- `services/credentials/vault.py` - Credential vault implementation
- `services/credentials/models.py` - Data models
- `scripts/credential_manager.py` - CLI tool
- `.credentials/vault.enc` - Encrypted credential storage
- `.gitignore` - Excludes `.credentials/` from version control

## License

Same as parent project.
