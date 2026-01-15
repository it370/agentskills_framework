# UUID and Module Name Migration Guide

## Overview

This migration implements three major schema changes:

1. **UUID Primary Keys**: Converts `users.id` and `dynamic_skills.id` from `BIGSERIAL` to `UUID`
2. **Module Name Column**: Adds `module_name` column to `dynamic_skills` table
3. **Auto-generation**: Automatically generates valid Python module names from skill names

## Why This Migration?

### UUID Benefits
- Better for distributed systems and microservices
- No collision risk across different database instances
- Better security (IDs are not sequential/predictable)
- Standard format for modern APIs

### Module Name Benefits
- Avoids runtime errors from invalid Python identifiers in skill names
- Separates display name (can have spaces, special chars) from internal module name
- Consistent, predictable module naming for dynamic skill registration
- Prevents issues with special characters in skill names like "Data Processing-2024" becoming invalid module names

## Migration Process

### For Existing Databases

**IMPORTANT**: This migration modifies primary keys. Always backup your database first!

```bash
# 1. Backup your database
pg_dump -U your_user -d your_database > backup_before_uuid_migration.sql

# 2. Run the migration
psql -U your_user -d your_database -f db/migrate_to_uuid_and_module_name.sql

# 3. Verify the migration
psql -U your_user -d your_database -c "SELECT id, username FROM users LIMIT 5;"
psql -U your_user -d your_database -c "SELECT id, name, module_name FROM dynamic_skills LIMIT 5;"
```

### For New Installations

The updated schema files (`users_schema.sql` and `dynamic_skills_schema.sql`) already include UUID primary keys and the module_name column. Just run:

```bash
python db/setup_database.py
```

## What Changes?

### Database Schema Changes

#### 1. Users Table
```sql
-- Before
id BIGSERIAL PRIMARY KEY

-- After
id UUID PRIMARY KEY DEFAULT uuid_generate_v4()
```

All foreign key references updated:
- `password_reset_tokens.user_id` → UUID
- `user_sessions.user_id` → UUID
- `run_metadata.user_id` → UUID (if exists)
- `logs.user_id` → UUID (if exists)

#### 2. Dynamic Skills Table
```sql
-- Before
id BIGSERIAL PRIMARY KEY
name TEXT UNIQUE NOT NULL

-- After
id UUID PRIMARY KEY DEFAULT uuid_generate_v4()
name TEXT UNIQUE NOT NULL
module_name TEXT UNIQUE NOT NULL
```

**Module Name Generation**:
- Converts to lowercase
- Replaces spaces and special characters with underscores
- Removes consecutive underscores
- Trims leading/trailing underscores

Examples:
- "Data Processing" → "data_processing"
- "Criminal-Verifier" → "criminal_verifier"
- "Agent Education 2024" → "agent_education_2024"
- "REST API Validator!" → "rest_api_validator"

### Code Changes

#### 1. Skill Manager (`skill_manager.py`)
- Updated `load_skills_from_database()` to fetch `module_name` column
- Updated `_register_inline_action()` to use `module_name` for Python module registration
- Updated `_register_pipeline_functions()` to use `module_name` for Python module registration

#### 2. Skills API (`api/skills_api.py`)
- Updated all SELECT queries to include `module_name`
- API responses now include `module_name` field

#### 3. Database Setup (`db/setup_database.py`)
- Added migration to the setup script (with warning for existing databases)

## Module Registration

### Before
```python
# Used skill name directly (could have spaces/special chars)
module_name = f"dynamic_skills.{skill_name}"  # ❌ Could be invalid
```

### After
```python
# Uses sanitized module_name from database
module_name = f"dynamic_skills.{module_name}"  # ✅ Always valid
```

## Testing the Migration

Run the test script to verify everything works:

```bash
python db/test_uuid_migration.py
```

This will:
1. Check that UUIDs are being used
2. Verify module_name is auto-generated correctly
3. Test skill registration with various name formats
4. Verify foreign key relationships work

## Rollback Plan

If you need to rollback:

1. Restore from backup:
```bash
psql -U your_user -d your_database < backup_before_uuid_migration.sql
```

2. Or manually revert (not recommended):
```sql
-- This is complex and data-dependent. Backup is strongly recommended instead.
```

## API Compatibility

### Breaking Changes
- All ID fields in API responses are now UUIDs instead of integers
- Example: `"id": "550e8400-e29b-41d4-a716-446655440000"` instead of `"id": 123`

### New Fields
- Skills API now returns `module_name` field
- Example response:
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "name": "Data Processing 2024",
  "module_name": "data_processing_2024",
  "description": "..."
}
```

## Troubleshooting

### Issue: Migration fails with "relation already exists"
**Solution**: The migration is idempotent. If it fails partway, you can re-run it. Existing objects will be skipped.

### Issue: Module name conflicts
**Solution**: The migration ensures `module_name` is unique. If two skills would generate the same module name, rename one before migration.

### Issue: UUIDs not generating
**Solution**: Ensure uuid-ossp extension is installed:
```sql
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
```

### Issue: Foreign key violations
**Solution**: The migration handles all foreign key updates automatically. If you see this error, check if you have custom tables referencing users or dynamic_skills.

## Performance Considerations

- UUID indexes are slightly larger than BIGINT indexes
- Module name trigger adds minimal overhead on INSERT/UPDATE
- Overall performance impact is negligible for normal workloads
- UUIDs are excellent for distributed systems and sharding

## Security Benefits

1. **Non-Sequential IDs**: UUIDs don't reveal record count or creation order
2. **Unpredictable**: Harder to guess valid IDs for enumeration attacks
3. **Module Name Sanitization**: Prevents code injection via skill names

## Future Considerations

- Consider using UUIDv7 for better database performance (requires PostgreSQL 13+)
- Module names are cached at registration time, changes require skill reload
- Foreign key cascades remain the same (CASCADE for sessions/tokens, SET NULL for user_id references)
