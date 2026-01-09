---
name: DatabaseUserFetcher
description: Fetch user profile data from PostgreSQL database
requires:
  - user_id
produces:
  - user_profile
  - profile_found
executor: action

action:
  type: data_query
  source: postgres
  query: "SELECT id, email, name, created_at, status FROM users WHERE id = {user_id}"
  credential_ref: "my_postgres_main"  # References credential in secure vault
  timeout: 10.0
---

# DatabaseUserFetcher

## Purpose
Fetch user profile directly from the database using SQL query with secure credentials.

## Security
- Uses secure credential vault for database access
- Credentials are user-isolated and encrypted (AES-256)
- Password never exposed in skill configuration

## Setup

### 1. Store your database credential
```bash
python -m scripts.credential_manager add \
  --user your_user_id \
  --name my_postgres_main \
  --db-type postgres
# Follow prompts to enter host, database, username, password
```

### 2. Reference in skill
The `credential_ref: "my_postgres_main"` in the action config above references
the credential you created. Each user has their own isolated credentials.

## Query Details
- **Database**: PostgreSQL
- **Table**: `users`
- **Columns**: id, email, name, created_at, status
- **Filter**: By user_id

## Notes
- Query is parameterized with `{user_id}` placeholder
- Framework automatically formats the query with input context
- Results are returned as JSON-serializable dict
- Connection pooling is handled by the framework

## Output Schema
- `user_profile`: Dict containing user data
- `profile_found`: Boolean indicating if user exists

## Example Usage

```python
from services.credentials import UserContext

result = await execute_skill(
    skill_name="DatabaseUserFetcher",
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

## Example Output
```json
{
  "query_result": [
    {
      "id": 123,
      "email": "user@example.com",
      "name": "John Doe",
      "created_at": "2024-01-01T00:00:00Z",
      "status": "active"
    }
  ],
  "row_count": 1
}
```
