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
  timeout: 10.0
---

# DatabaseUserFetcher

## Purpose
Fetch user profile directly from the database using SQL query.
This demonstrates the `data_query` action type for direct database access.

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
