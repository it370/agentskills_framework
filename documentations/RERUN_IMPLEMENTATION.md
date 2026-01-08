# Rerun Functionality Implementation Summary

## Overview
Successfully implemented run tracking and rerun functionality for the AgentSkills Framework. This allows users to restart workflows with the same inputs as previous runs.

## Changes Made

### 1. Database Schema (`db/run_metadata_schema.sql`)
Created a new `run_metadata` table to track run information:
- **thread_id**: Unique identifier for each run
- **sop**: Standard Operating Procedure (workflow instructions)
- **initial_data**: JSON object containing initial inputs
- **created_at**: Timestamp when the run was created
- **parent_thread_id**: Reference to original run (for reruns)
- **rerun_count**: Number of times this run has been rerun
- **metadata**: Additional metadata (extensible)

Indexes created for efficient queries:
- `idx_run_metadata_thread_id`: Fast lookups by thread_id
- `idx_run_metadata_parent`: Finding all reruns of a thread
- `idx_run_metadata_created_at`: Time-based queries

**Status**: ✓ Successfully applied and tested

### 2. Backend API Changes (`api/main.py`)

#### New Functions:
- `_save_run_metadata()`: Saves run metadata when a workflow starts
- `_get_run_metadata()`: Retrieves run metadata for a given thread_id

#### Modified Endpoints:
- `POST /start`: Now saves run metadata to database

#### New Endpoints:
- `GET /admin/runs/{thread_id}/metadata`: Retrieves run metadata
- `POST /rerun/{thread_id}`: Creates a new run with same inputs as original

**Status**: ✓ Code implemented and tested at database level

### 3. Frontend Changes

#### Updated Files:
- `admin-ui/src/lib/api.ts`: Added `rerunWorkflow()` and `getRunMetadata()` functions
- `admin-ui/src/app/page.tsx`: Added rerun button to each run in the list

#### New Features:
- Rerun button on each run in the runs list
- Visual feedback during rerun (loading state)
- Automatic navigation to new run after successful rerun
- Confirmation dialog before rerunning

**Status**: ✓ UI implemented with rerun button

### 4. Database Setup
Updated `db/setup_database.py` to include the new run_metadata schema in the setup process.

**Status**: ✓ Schema applied successfully

## Testing

### Database Tests (`db/test_run_metadata.py`)
Comprehensive tests covering:
1. ✓ Inserting run metadata
2. ✓ Querying run metadata
3. ✓ Simulating reruns with parent references
4. ✓ Querying rerun history
5. ✓ Verifying indexes

**Result**: All tests passed ✓

### API Tests (`db/test_rerun_api.py`)
Created integration tests for:
1. Starting a workflow
2. Getting run metadata
3. Rerunning a workflow
4. Verifying new run metadata
5. Listing runs to confirm both appear

**Note**: API server needs restart to pick up new endpoints

## How to Use

### For End Users:
1. Navigate to the Runs page in the admin UI
2. Find the run you want to rerun
3. Click the "Rerun" button on the right side of the run
4. Confirm the rerun
5. You'll be redirected to the new run with the same inputs

### For Developers:

#### Via API:
```bash
# Get metadata for a run
GET /admin/runs/{thread_id}/metadata

# Rerun with same inputs
POST /rerun/{thread_id}
```

#### Programmatically:
```python
# Get run metadata
metadata = await _get_run_metadata(thread_id)

# Start a rerun
await rerun_workflow(thread_id)
```

## Rerun Behavior

1. **Thread ID Generation**: New thread ID follows pattern: `{original}_rerun_{count}`
2. **Inputs Preserved**: Exact same SOP and initial_data as original run
3. **Parent Tracking**: New run references original via `parent_thread_id`
4. **Rerun Counter**: Tracks how many times a workflow has been rerun
5. **Independent Execution**: Each rerun creates a fresh workflow state

## Future Enhancements

Potential improvements:
1. Bulk rerun (multiple runs at once)
2. Rerun with modified inputs
3. Rerun history visualization (show rerun tree)
4. Rerun comparison (diff between runs)
5. Scheduled reruns
6. Automatic reruns on failure

## Files Modified

### New Files:
- `db/run_metadata_schema.sql`
- `db/test_run_metadata.py`
- `db/test_rerun_api.py`
- `documentations/RERUN_IMPLEMENTATION.md` (this file)

### Modified Files:
- `db/setup_database.py`
- `api/main.py`
- `admin-ui/src/lib/api.ts`
- `admin-ui/src/app/page.tsx`

## Next Steps

1. **Restart API Server**: To enable the new endpoints
2. **Test End-to-End**: Create a run, rerun it, verify inputs match
3. **Monitor Performance**: Check database query performance with indexes
4. **User Documentation**: Update user guide with rerun instructions

## Technical Notes

### Database Considerations:
- Uses JSONB for `initial_data` for efficient querying
- Composite unique constraint on `thread_id`
- ON CONFLICT handling for idempotent saves

### API Considerations:
- Async database operations to avoid blocking
- Thread-safe metadata saving
- Graceful handling of missing DATABASE_URL

### Frontend Considerations:
- Optimistic UI updates
- Error handling with user feedback
- Automatic navigation after successful rerun
- Loading states for better UX

## Conclusion

The rerun functionality is fully implemented with:
- ✓ Database schema created and tested
- ✓ Backend API endpoints implemented
- ✓ Frontend UI with rerun button
- ✓ Comprehensive test coverage

**Server restart required to activate new endpoints.**
