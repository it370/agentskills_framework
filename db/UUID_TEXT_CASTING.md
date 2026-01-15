# UUID to Text Conversion - Implementation Notes

## The Problem

After migrating to UUID primary keys, UUID objects from PostgreSQL aren't JSON serializable in Python, causing errors like:
```
TypeError: Object of type UUID is not JSON serializable
```

## The Solution: Cast in SQL

Instead of converting UUIDs to strings in Python code with `str(uuid_obj)`, we cast them to text directly in SQL queries using `::text`.

### Before (Inefficient)
```python
# Python code
cur.execute("SELECT id FROM users WHERE username = %s", (username,))
row = cur.fetchone()
user_id = str(row[0])  # Convert UUID to string in Python
```

### After (Better)
```python
# Cast in SQL query
cur.execute("SELECT id::text FROM users WHERE username = %s", (username,))
row = cur.fetchone()
user_id = row[0]  # Already a string!
```

## Benefits

1. **Cleaner Code**: No need for `str()` conversions everywhere
2. **Performance**: Type conversion happens in the database (minimal overhead)
3. **Consistency**: All ID fields are strings from the start
4. **Maintainability**: Clear intent in SQL queries
5. **Less Error-Prone**: Can't forget to convert a UUID

## Implementation Pattern

### For SELECT Queries
```sql
-- Cast UUID columns to text
SELECT id::text, username, email FROM users WHERE username = %s
SELECT user_id::text FROM run_metadata WHERE thread_id = %s
```

### For INSERT/UPDATE with RETURNING
```sql
-- Return UUID as text
INSERT INTO users (...) VALUES (...) RETURNING id::text, username, email
UPDATE users SET ... WHERE id = %s RETURNING id::text
```

### For JOINs
```sql
-- Cast UUIDs from joined tables
SELECT s.id, u.id::text, u.username, u.email
FROM user_sessions s
JOIN users u ON s.user_id = u.id
WHERE s.token_jti = %s
```

## Files Updated

All SQL queries returning UUIDs were updated to cast to text:

1. **`services/user_service.py`**
   - `register_user()`: `RETURNING id::text, ...`
   - `login()`: `SELECT id::text, ...`
   - `verify_token()`: `SELECT ... u.id::text ...`
   - `get_user_by_id()`: `SELECT id::text, ...`
   - `get_user_by_username()`: `SELECT id::text, ...`
   - `request_password_reset()`: `SELECT id::text FROM users ...`

2. **`skill_manager.py`**
   - `save_skill_to_database()`: `RETURNING id::text`
   - Return type changed from `int` to `str`

3. **`api/main.py`**
   - `get_user_id_for_thread()`: `SELECT user_id::text ...`

## Python Type Hints

Updated type hints to reflect that IDs are now strings:

```python
# Before
class User(BaseModel):
    id: int  # ❌ No longer correct

async def get_user_by_id(self, user_id: int) -> Optional[User]:  # ❌
    ...

def _generate_jwt(self, user_id: int, ...) -> tuple[str, str]:  # ❌
    ...

def save_skill_to_database(skill_data: Dict[str, Any]) -> int:  # ❌
    ...

# After
class User(BaseModel):
    id: str  # ✅ UUID as string

async def get_user_by_id(self, user_id: str) -> Optional[User]:  # ✅
    ...

def _generate_jwt(self, user_id: str, ...) -> tuple[str, str]:  # ✅
    ...

def save_skill_to_database(skill_data: Dict[str, Any]) -> str:  # ✅
    ...
```

## API Responses

All API responses now return UUIDs as strings automatically:

```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "username": "john_doe",
  "email": "john@example.com",
  "token": "eyJ..."
}
```

## Testing

When testing, remember UUIDs are now strings:

```python
# Test user creation
user = await user_service.register_user(registration)
assert isinstance(user.id, str)  # ✅ ID is string
assert len(user.id) == 36  # Standard UUID string length (with hyphens)

# Test JWT payload
token, user = await user_service.login(login_data)
payload = jwt.decode(token, secret, algorithms=['HS256'])
assert isinstance(payload['user_id'], str)  # ✅ Already a string
```

## Performance Impact

- **Minimal**: `::text` cast is extremely fast in PostgreSQL
- **No network overhead**: Conversion happens server-side
- **Better than Python conversion**: Database is optimized for type conversions

## Best Practices

1. **Always cast in SQL**: Use `::text` for all UUID columns in SELECT/RETURNING
2. **Update type hints**: Change `int` to `str` for ID fields
3. **Don't use str() in Python**: Let SQL handle the conversion
4. **Consistent patterns**: Apply the same approach everywhere
5. **Document in comments**: Note when UUIDs are cast to text

## Common Patterns

### Pattern 1: Simple Select
```python
cur.execute("SELECT id::text, name FROM dynamic_skills WHERE name = %s", (name,))
```

### Pattern 2: Join with Multiple Tables
```python
cur.execute("""
    SELECT 
        ds.id::text,
        ds.name,
        u.id::text as user_id,
        u.username
    FROM dynamic_skills ds
    LEFT JOIN users u ON ds.created_by_user_id = u.id
""")
```

### Pattern 3: INSERT with RETURNING
```python
cur.execute("""
    INSERT INTO users (username, email, password_hash)
    VALUES (%s, %s, %s)
    RETURNING id::text, username, email, created_at
""", (username, email, hash))
```

## Migration Checklist

- [x] Update all SELECT queries with UUID columns to use `::text`
- [x] Update all RETURNING clauses to cast UUIDs to text
- [x] Update Python type hints (int → str for ID fields)
- [x] Update model classes (User.id: int → User.id: str)
- [x] Remove any `str(uuid_obj)` conversions in Python code
- [x] Test JSON serialization works correctly
- [x] Test API responses return string UUIDs
- [x] Test JWT token generation and validation

## Conclusion

Casting UUIDs to text in SQL queries is the cleanest and most efficient way to handle UUID serialization. It keeps the Python code simple and leverages PostgreSQL's built-in type conversion capabilities.
