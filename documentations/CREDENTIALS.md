# Secure Credential Management System

Complete guide for managing database credentials securely in the AgentSkills framework.

## Table of Contents

1. [Overview](#overview)
2. [Quick Start](#quick-start)
3. [Setup](#setup)
4. [CLI Commands](#cli-commands)
5. [Using Credentials in Skills](#using-credentials-in-skills)
6. [Global Auth Context](#global-auth-context)
7. [Without User Authentication](#without-user-authentication)
8. [Python API](#python-api)
9. [Security Features](#security-features)
10. [Troubleshooting](#troubleshooting)

---

## Overview

The credential management system provides:

- **Encrypted Storage** - AES-256 encryption for passwords at rest
- **User Isolation** - Each user can only access their own credentials
- **Simple Integration** - Direct `credential_ref` in skill.md
- **Credential Rotation** - Update passwords without changing skills
- **Multi-Database Support** - PostgreSQL, MySQL, MongoDB, Redis
- **CLI Management** - Full command-line interface for CRUD operations

### Architecture

```
Skills (skill.md)
    ↓ credential_ref: "my_db"
Engine (engine.py)
    ↓ resolve credential
CredentialVault (vault.py)
    ↓ decrypt password
    ↓ build connection string
Database Connection
```

---

## Quick Start

### 1. Install Dependencies

```bash
conda activate clearstar
pip install cryptography
```

### 2. Generate Master Key

```bash
# Generate a secure master key
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

# Save to .env file
echo "CREDENTIAL_MASTER_KEY=<your-generated-key>" >> .env
```

### 3. Add a Credential

```bash
python -m scripts.credential_manager add --user system --name my_postgres
```

Follow the prompts to enter database details.

### 4. Use in Skill

In your `skill.md`:

```yaml
---
name: DatabaseUserFetcher
action:
  type: data_query
  source: postgres
  credential_ref: "my_postgres"  # References credential in vault
  query: "SELECT * FROM users WHERE id = {user_id}"
---
```

### 5. Initialize Global Auth (in main.py)

```python
from services.credentials import AuthContext
from env_loader import load_env_once

load_env_once()
AuthContext.initialize_from_env()  # Uses system user by default
```

That's it! Skills will automatically use secure credentials.

---

## Setup

### Step 1: Environment Configuration

Create or edit `.env` file:

```bash
# Required: Master encryption key
CREDENTIAL_MASTER_KEY=<your-generated-key>

# Optional: Default user settings
DEFAULT_USER_ID=system
DEFAULT_USER_ADMIN=true
```

**Generate master key:**

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

### Step 2: Add to .gitignore

Ensure sensitive files are not committed:

```gitignore
# Environment variables
.env
.env.local

# Encrypted credentials
.credentials/
*.enc
```

### Step 3: Initialize in Application

In your `main.py`:

```python
from env_loader import load_env_once
from services.credentials import AuthContext

# Load environment variables
load_env_once()

# Initialize global authentication context
AuthContext.initialize_from_env()
```

---

## CLI Commands

### Add Credential

```bash
# Interactive mode (recommended)
python -m scripts.credential_manager add --user system --name my_postgres

# Non-interactive mode (all parameters)
python -m scripts.credential_manager add \
  --user system \
  --name my_postgres \
  --db-type postgres \
  --host localhost \
  --port 5432 \
  --database mydb \
  --username myuser \
  --password "mypassword" \
  --description "Production database"
```

### List Credentials

```bash
python -m scripts.credential_manager list --user system
```

Output:
```
Credentials for user system:
================================================================================

📁 my_postgres
   ID:          system_my_postgres_1234567890.123456
   Type:        postgres
   Host:        localhost:5432
   Database:    mydb
   Username:    myuser
   Created:     2026-01-09T10:30:00
   Updated:     2026-01-09T10:30:00
   Description: Production database

================================================================================
Total: 1 credential(s)
```

### Test Credential

```bash
python -m scripts.credential_manager test --user system --name my_postgres
```

Shows masked connection string (safe for production):
```
✅ Credential 'my_postgres' is valid
   Connection string: postgresql://myuser:****@localhost:5432/mydb
   Type: postgres
   Host: localhost:5432
   Database: mydb
```

### Show Credential (Dev/Test Only!)

```bash
python -m scripts.credential_manager show --user system --name my_postgres
```

Shows plaintext password (dev/test only):
```
======================================================================
WARNING: DISPLAYING PLAINTEXT PASSWORD - DEV/TEST ONLY!
======================================================================

Credential: my_postgres
  Type: postgres
  Host: localhost
  Port: 5432
  Database: mydb
  Username: myuser
  Password: MySecretPass123!

Connection String:
  postgresql://myuser:MySecretPass123!@localhost:5432/mydb
```

⚠️ **Never use `show` in production!** Use `test` for safe verification.

### Update Password

```bash
# Interactive (secure)
python -m scripts.credential_manager update --user system --name my_postgres

# Command line (not recommended)
python -m scripts.credential_manager update --user system --name my_postgres --password "newpass"
```

### Delete Credential

```bash
# With confirmation prompt
python -m scripts.credential_manager delete --user system --name my_postgres

# Skip confirmation
python -m scripts.credential_manager delete --user system --name my_postgres --yes
```

---

## Using Credentials in Skills

### Basic Usage

In your `skills/YourSkill/skill.md`:

```yaml
---
name: YourSkill
description: Fetch data from database
requires:
  - query_param
produces:
  - result_data
executor: action

action:
  type: data_query
  source: postgres
  credential_ref: "my_postgres"  # Reference credential by name
  query: "SELECT * FROM table WHERE id = {query_param}"
---
```

### Supported Database Types

#### PostgreSQL

```yaml
action:
  type: data_query
  source: postgres
  credential_ref: "my_postgres"
  query: "SELECT * FROM users WHERE id = {user_id}"
```

#### MySQL

```yaml
action:
  type: data_query
  source: mysql
  credential_ref: "my_mysql"
  query: "SELECT * FROM orders WHERE customer_id = {customer_id}"
```

#### MongoDB

```yaml
action:
  type: data_query
  source: mongodb
  credential_ref: "my_mongo"
  collection: "users"
  filter: {"user_id": "{user_id}"}
```

### Execution

Skills automatically use credentials from the vault:

```python
from engine import execute_skill

# Execute skill - credentials resolved automatically
result = await execute_skill(
    skill_name="DatabaseUserFetcher",
    inputs={
        "user_id": 123
        # No need to pass credentials or user_context if global auth is set up
    }
)
```

---

## Global Auth Context

Initialize once at startup, use everywhere automatically.

### Setup in main.py

```python
from services.credentials import AuthContext
from env_loader import load_env_once

# Load environment
load_env_once()

# Initialize global auth context
# Uses DEFAULT_USER_ID from .env (defaults to "system")
AuthContext.initialize_from_env()
```

### Use Anywhere

```python
from services.credentials import get_current_user

# Get current user context automatically
user = get_current_user()

print(f"Current user: {user.user_id}")
# Output: Current user: system
```

### Benefits

✅ **Initialize once** - At application startup
✅ **Access anywhere** - No need to pass user_context around
✅ **Skills auto-use** - Credentials resolved automatically
✅ **Cleaner code** - Less boilerplate

### Manual Initialization (Alternative)

```python
from services.credentials import AuthContext, get_system_user

# Initialize with system user
AuthContext.initialize(get_system_user())

# Or with custom user
from services.credentials import UserContext
custom_user = UserContext(
    user_id="myapp",
    username="myapp@system",
    roles=["admin", "user"]
)
AuthContext.initialize(custom_user)
```

---

## Without User Authentication

If you don't have user authentication, use the system user.

### Option 1: System User (Recommended)

```bash
# Store credentials for system user
python -m scripts.credential_manager add --user system --name my_db
```

In your code:

```python
from services.credentials import get_system_user

# Get system user
user = get_system_user()

# Execute skill
result = await execute_skill(
    skill_name="DatabaseUserFetcher",
    inputs={
        "user_id": 123,
        "user_context": user  # Use system user
    }
)
```

### Option 2: Global Auth Context (Simpler)

```python
# In main.py (once at startup)
from services.credentials import AuthContext
AuthContext.initialize_from_env()  # Automatically uses system user

# Everywhere else - no need to pass user_context!
result = await execute_skill(
    skill_name="DatabaseUserFetcher",
    inputs={"user_id": 123}  # That's it!
)
```

### Option 3: Environment-Based User

```bash
# Set default user in .env
export DEFAULT_USER_ID="myapp"
```

```python
from services.credentials import get_default_user

user = get_default_user()  # Uses DEFAULT_USER_ID from env
```

### Migration Path

When you add user authentication later:

```python
# Before (no auth)
user = get_system_user()

# After (with auth) - just change this one line!
user = UserContext(
    user_id=authenticated_user.id,
    username=authenticated_user.email,
    roles=authenticated_user.roles
)

# Rest of your code stays the same!
```

---

## Python API

### Get Vault

```python
from services.credentials import get_vault, get_system_user

vault = get_vault()
user = get_system_user()
```

### Store Credential

```python
cred_id = vault.store_credential(
    user_context=user,
    name="my_postgres",
    db_type="postgres",
    host="localhost",
    port=5432,
    database="mydb",
    username="myuser",
    password="mypassword",
    description="Production database"
)
```

### Get Credential

```python
credential = vault.get_credential(user, "my_postgres")

# Access properties
print(credential.host)        # localhost
print(credential.port)        # 5432
print(credential.database)    # mydb
print(credential.username)    # myuser
```

### Get Decrypted Password

```python
password = vault.get_decrypted_password(credential)
# Use with caution - only in memory, never log!
```

### Build Connection String

```python
conn_str = vault.build_connection_string(credential)
# postgresql://myuser:mypassword@localhost:5432/mydb
```

### List Credentials

```python
credentials = vault.list_credentials(user)

for cred in credentials:
    print(f"{cred.name}: {cred.db_type} @ {cred.host}")
```

### Update Password

```python
vault.update_password(user, "my_postgres", "new_password")
```

### Delete Credential

```python
vault.delete_credential(user, "my_postgres")
```

### User Context

```python
from services.credentials import UserContext

# Create user context
user = UserContext(
    user_id="alice",
    username="alice@example.com",
    roles=["user"]
)

# Check if admin
if user.is_admin():
    print("User is admin")

# Check if has role
if user.has_role("user"):
    print("User has 'user' role")
```

---

## Security Features

### Encryption

- **Algorithm**: AES-256 (Fernet)
- **Master Key**: Stored in environment variable
- **At Rest**: All passwords encrypted in vault file
- **In Memory**: Decrypted only when needed

### User Isolation

- Users can only access their own credentials
- Credentials stored with owner_id
- Authorization checked on every access
- Admin role can access all credentials

### Credential Rotation

```python
# Update password - skills automatically use new password
vault.update_password(user, "my_postgres", "new_password")

# No need to update skill.md or restart application!
```

### Audit Trail

Each credential stores:
- Created timestamp
- Updated timestamp
- Owner user ID

### Best Practices

1. ✅ **Never commit** `.env` or `.credentials/` to git
2. ✅ **Use interactive mode** when adding credentials (avoids shell history)
3. ✅ **Rotate regularly** - Update passwords periodically
4. ✅ **Use `test` command** - Not `show` (unless debugging in dev)
5. ✅ **One master key** per environment (dev/staging/prod)
6. ✅ **Backup vault file** - But keep it encrypted
7. ✅ **Separate users** - Don't share system user in multi-tenant apps

### File Locations

```
.env                    # Master key (DO NOT COMMIT)
.credentials/
  vault.enc            # Encrypted credentials (DO NOT COMMIT)
```

---

## Troubleshooting

### "No credentials found for user X"

**Cause**: Credential doesn't exist or belongs to different user

**Solution**:
```bash
# List credentials to verify
python -m scripts.credential_manager list --user X

# Make sure you're using the correct user ID
```

### "Error loading credentials" / Auto-generated key warning

**Cause**: `CREDENTIAL_MASTER_KEY` not set in `.env`

**Solution**:
```bash
# Generate key
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

# Add to .env
echo "CREDENTIAL_MASTER_KEY=<your-key>" >> .env

# Delete old vault (was encrypted with temp key)
rm .credentials/vault.enc

# Re-add credentials
```

### "AuthContext not initialized"

**Cause**: Global auth context not set up

**Solution**:
```python
# In main.py at startup
from services.credentials import AuthContext
from env_loader import load_env_once

load_env_once()
AuthContext.initialize_from_env()
```

### "Failed to resolve credential"

**Cause**: `credential_ref` not found in vault

**Solution**:
1. Verify credential exists: `python -m scripts.credential_manager list --user system`
2. Check spelling in skill.md matches credential name exactly
3. Ensure global auth is initialized

### Connection fails with correct credentials

**Cause**: Database host/port not accessible

**Solution**:
```bash
# Test credential to see connection string
python -m scripts.credential_manager test --user system --name my_postgres

# Verify you can reach the database
ping <host>
telnet <host> <port>
```

### Unicode/Emoji errors on Windows

**Cause**: Windows console encoding issues

**Solution**: Already fixed - the CLI now uses ASCII text instead of emojis.

---

## Command Reference

```bash
# Add credential
python -m scripts.credential_manager add --user <user> --name <name>

# List credentials
python -m scripts.credential_manager list --user <user>

# Test credential (password masked - safe)
python -m scripts.credential_manager test --user <user> --name <name>

# Show credential (password visible - dev only!)
python -m scripts.credential_manager show --user <user> --name <name>

# Update password
python -m scripts.credential_manager update --user <user> --name <name>

# Delete credential
python -m scripts.credential_manager delete --user <user> --name <name> [--yes]

# Help
python -m scripts.credential_manager --help
python -m scripts.credential_manager <command> --help
```

---

## Summary

The credential management system provides enterprise-grade security for database credentials while maintaining simplicity:

1. **Setup**: Generate master key, add to `.env`
2. **Add**: Use CLI to store credentials securely
3. **Use**: Reference by name in skill.md with `credential_ref`
4. **Execute**: Skills automatically resolve and use credentials
5. **Rotate**: Update passwords without changing code

All passwords are encrypted at rest, user-isolated, and never exposed in code or config files.

For more information, see:
- `services/credentials/` - Implementation
- `scripts/credential_manager.py` - CLI tool
- `engine.py` - Credential resolution in action execution
