# Run Manager Feature

## Overview

The Run Manager is an admin-only feature that provides a compact, data-dense interface for managing workflow runs with advanced filtering and bulk deletion capabilities.

## Features

### 1. Simplified Data Display
- Tabular view showing only essential information:
  - **ID**: Thread ID (truncated for display)
  - **Name**: Run name (or thread ID if no name)
  - **Status**: Running, Completed, Error, or Paused
  - **Time**: Creation timestamp
  - **Username**: User who started the run
  - **Workspace**: Workspace ID

### 2. Advanced Filtering
- **Search**: Full-text search across thread IDs and run names
- **Username Filter**: Dropdown to filter by specific users
- **Workspace Filter**: Dropdown to filter by specific workspaces
- All filters work together and reset pagination automatically

### 3. Pagination
- Default: 50 runs per page
- Configurable page size (1-200 items)
- Navigation controls with page indicators

### 4. Bulk Operations
- **Select All**: Checkbox to select all runs on current page
- **Individual Selection**: Checkbox per row
- **Bulk Delete**: Delete multiple runs at once with confirmation

### 5. Deletion Features
- Completely removes all traces of selected runs:
  - run_metadata entries
  - checkpoints (from checkpoints table)
  - checkpoint_writes
  - logs
- Confirmation dialog before deletion
- Reports success/failure counts
- Handles partial failures gracefully

## Backend API Endpoints

All endpoints are admin-only and prefixed with `/admin/run-manager`.

### GET `/admin/run-manager/runs`
List all runs with pagination and filtering.

**Query Parameters:**
- `page` (int, default=1): Page number (1-indexed)
- `page_size` (int, default=50): Items per page (1-200)
- `username` (string, optional): Filter by username
- `workspace` (string, optional): Filter by workspace ID
- `search` (string, optional): Search in thread_id or run_name

**Response:**
```json
{
  "runs": [
    {
      "id": "thread_abc123",
      "name": "Order Processing",
      "result": "completed",
      "time": "2026-02-05T10:30:00Z",
      "username": "john.doe",
      "workspace": "workspace_xyz"
    }
  ],
  "total": 150,
  "page": 1,
  "page_size": 50
}
```

### DELETE `/admin/run-manager/runs`
Bulk delete runs with all their data.

**Request Body:**
```json
{
  "thread_ids": ["thread_1", "thread_2", "thread_3"]
}
```

**Response:**
```json
{
  "deleted_count": 3,
  "failed": []
}
```

If some deletions fail:
```json
{
  "deleted_count": 2,
  "failed": [
    {
      "thread_id": "thread_3",
      "error": "Foreign key constraint violation"
    }
  ]
}
```

### GET `/admin/run-manager/usernames`
Get list of all unique usernames that have runs.

**Response:**
```json
{
  "usernames": ["john.doe", "jane.smith", "admin"]
}
```

### GET `/admin/run-manager/workspaces`
Get list of all unique workspace IDs that have runs.

**Response:**
```json
{
  "workspaces": ["workspace_1", "workspace_2", "workspace_3"]
}
```

## Frontend Implementation

### Location
`/admin-ui/src/app/run-manager/page.tsx`

### Navigation
- Added to sidebar navigation for admin users only
- Icon: Database icon
- Visible when `user.is_admin === true`

### Key Components

#### RunManagerPage
Main page component with state management for:
- Run list
- Pagination
- Filters
- Selection
- Delete operations

#### StatusBadge
Reusable component for displaying run status with color coding:
- Running: Blue
- Completed: Green
- Error: Red
- Paused: Yellow
- Unknown: Gray

### User Experience

1. **Access Control**: Page redirects non-admin users to home
2. **Loading States**: Spinner shown during data fetching
3. **Error Handling**: Error messages displayed in alert boxes
4. **Confirmation Dialogs**: Delete confirmation modal with count
5. **Real-time Feedback**: Success/failure alerts after operations
6. **Responsive Design**: Works on desktop and tablet screens
7. **Click Navigation**: Click any row to view run details

## Database Schema

No new tables required. Uses existing tables:
- `run_metadata`: Main run information
- `users`: For username joins
- `checkpoints`: Checkpoint data
- `checkpoint_writes`: Checkpoint write operations
- `logs`: Run logs

**Note**: The backend automatically converts UUID fields (workspace_id, user_id) to strings for JSON serialization.

## Security

- All endpoints require admin authentication via `AdminUser` dependency
- JWT token validation
- No workspace isolation for admin views (admins see all workspaces)

## Testing

### Manual Testing Steps

1. **Access Control**
   - Login as admin → should see "Run Manager" in navigation
   - Login as regular user → should NOT see "Run Manager"

2. **Data Display**
   - Navigate to Run Manager
   - Verify all runs are displayed
   - Check pagination controls

3. **Filtering**
   - Test search by thread ID
   - Test search by run name
   - Test username filter
   - Test workspace filter
   - Test combined filters

4. **Selection**
   - Select individual runs
   - Use "Select All" checkbox
   - Verify selection count updates

5. **Deletion**
   - Select one or more runs
   - Click "Delete Selected"
   - Confirm in modal
   - Verify success message
   - Verify runs are removed from list
   - Check database to confirm deletion

6. **Error Handling**
   - Try to delete with foreign key issues
   - Verify error messages are clear
   - Verify partial success is reported

## Future Enhancements

Potential improvements:
- Export runs to CSV/JSON
- Bulk status updates
- Bulk rerun operations
- Advanced search with date ranges
- Column sorting
- Customizable columns
- Run comparison view
- Batch archiving instead of deletion

## Files Modified/Created

### Backend
- `api/run_manager_api.py` (new) - Run manager endpoints
- `api/main.py` (modified) - Added router import and registration

### Frontend
- `admin-ui/src/app/run-manager/page.tsx` (new) - Run manager page
- `admin-ui/src/lib/api.ts` (modified) - Added run manager API functions
- `admin-ui/src/components/DashboardLayout.tsx` (modified) - Added navigation item
