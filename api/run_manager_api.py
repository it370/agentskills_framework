"""
Run Manager API - Simplified endpoints for run management with bulk operations
"""
import asyncio
from typing import Optional, List
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from services.auth_middleware import AdminUser
from services.connection_pool import get_postgres_pool
from log_stream import emit_log

router = APIRouter(prefix="/admin/run-manager", tags=["run-manager"])


class RunListItem(BaseModel):
    """Simplified run list item for data-dense tabular display"""
    id: str  # thread_id
    name: Optional[str]  # run_name
    result: Optional[str]  # status
    time: Optional[str]  # created_at
    username: Optional[str]  # from user_id join
    workspace: Optional[str]  # workspace_id
    workspace_name: Optional[str]  # workspace name for display


class RunListResponse(BaseModel):
    """Paginated run list response"""
    runs: List[RunListItem]
    total: int
    page: int
    page_size: int


class BulkDeleteRequest(BaseModel):
    """Request to delete one or more runs"""
    thread_ids: List[str]


class BulkDeleteResponse(BaseModel):
    """Response from bulk delete operation"""
    deleted_count: int
    failed: List[dict]  # List of {thread_id, error} for any failures


@router.get("/runs", response_model=RunListResponse)
async def list_runs_simplified(
    current_user: AdminUser,
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(50, ge=1, le=200, description="Items per page"),
    username: Optional[str] = Query(None, description="Filter by username"),
    workspace: Optional[str] = Query(None, description="Filter by workspace ID"),
    search: Optional[str] = Query(None, description="Search in thread_id, run_name"),
):
    """
    List all runs with simplified data for tabular display.
    Admin-only endpoint with pagination, filtering, and search.
    """
    pool = get_postgres_pool()
    
    def _fetch_runs():
        conn = pool.getconn()
        try:
            with conn.cursor() as cur:
                # Build WHERE clause dynamically
                where_clauses = []
                params = []
                
                if username:
                    where_clauses.append("u.username = %s")
                    params.append(username)
                
                if workspace:
                    where_clauses.append("rm.workspace_id = %s")
                    params.append(workspace)
                
                if search:
                    where_clauses.append("(rm.thread_id ILIKE %s OR rm.run_name ILIKE %s)")
                    search_param = f"%{search}%"
                    params.extend([search_param, search_param])
                
                where_sql = " AND ".join(where_clauses) if where_clauses else "TRUE"
                
                # Get total count
                count_sql = f"""
                    SELECT COUNT(*)
                    FROM run_metadata rm
                    LEFT JOIN users u ON rm.user_id = u.id
                    WHERE {where_sql}
                """
                cur.execute(count_sql, params)
                total = cur.fetchone()[0]
                
                # Get paginated results
                offset = (page - 1) * page_size
                list_sql = f"""
                    SELECT
                        rm.thread_id,
                        rm.run_name,
                        rm.status,
                        rm.created_at,
                        u.username,
                        rm.workspace_id,
                        w.name as workspace_name
                    FROM run_metadata rm
                    LEFT JOIN users u ON rm.user_id = u.id
                    LEFT JOIN workspaces w ON rm.workspace_id = w.id
                    WHERE {where_sql}
                    ORDER BY rm.created_at DESC NULLS LAST
                    LIMIT %s OFFSET %s
                """
                cur.execute(list_sql, params + [page_size, offset])
                rows = cur.fetchall()
                
                runs = [
                    RunListItem(
                        id=row[0],
                        name=row[1] or row[0],  # Fallback to thread_id if no run_name
                        result=row[2],
                        time=row[3].isoformat() if row[3] else None,
                        username=row[4],
                        workspace=str(row[5]) if row[5] else None,  # Convert UUID to string
                        workspace_name=row[6],
                    )
                    for row in rows
                ]
                
                return runs, total
        finally:
            pool.putconn(conn)
    
    try:
        runs, total = await asyncio.to_thread(_fetch_runs)
        return RunListResponse(
            runs=runs,
            total=total,
            page=page,
            page_size=page_size,
        )
    except Exception as e:
        emit_log(f"[RUN_MANAGER] Failed to fetch runs: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch runs: {str(e)}")


@router.delete("/runs", response_model=BulkDeleteResponse)
async def delete_runs_bulk(
    current_user: AdminUser,
    request: BulkDeleteRequest,
):
    """
    Delete one or more runs completely (all traces).
    Admin-only endpoint.
    
    Deletes:
    - run_metadata entry
    - checkpoints (from checkpoints table)
    - checkpoint_writes
    - logs
    """
    if not request.thread_ids:
        raise HTTPException(status_code=400, detail="No thread_ids provided")
    
    pool = get_postgres_pool()
    deleted_count = 0
    failed = []
    
    def _delete_run(thread_id: str):
        """Delete all traces of a single run"""
        conn = pool.getconn()
        try:
            with conn.cursor() as cur:
                # Delete in order to respect foreign key constraints
                # Note: No foreign keys exist, but we delete children before parents for safety
                
                # 1. checkpoint_writes (child of checkpoints)
                cur.execute("""
                    DELETE FROM checkpoint_writes
                    WHERE thread_id = %s
                """, (thread_id,))
                
                # 2. checkpoint_blobs (child of checkpoints)
                cur.execute("""
                    DELETE FROM checkpoint_blobs
                    WHERE thread_id = %s
                """, (thread_id,))
                
                # 3. checkpoints
                cur.execute("""
                    DELETE FROM checkpoints
                    WHERE thread_id = %s
                """, (thread_id,))
                
                # 4. thread_logs (not logs!)
                cur.execute("""
                    DELETE FROM thread_logs
                    WHERE thread_id = %s
                """, (thread_id,))
                
                # 5. run_metadata
                cur.execute("""
                    DELETE FROM run_metadata
                    WHERE thread_id = %s
                """, (thread_id,))
                
                conn.commit()
                return True
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            pool.putconn(conn)
    
    for thread_id in request.thread_ids:
        try:
            await asyncio.to_thread(_delete_run, thread_id)
            deleted_count += 1
            emit_log(f"[RUN_MANAGER] Deleted run: {thread_id}")
        except Exception as e:
            error_msg = str(e)
            emit_log(f"[RUN_MANAGER] Failed to delete run {thread_id}: {error_msg}")
            failed.append({"thread_id": thread_id, "error": error_msg})
    
    return BulkDeleteResponse(
        deleted_count=deleted_count,
        failed=failed,
    )


@router.get("/usernames")
async def list_usernames(current_user: AdminUser):
    """
    Get list of all unique usernames that have runs.
    Used for filter dropdown.
    """
    pool = get_postgres_pool()
    
    def _fetch_usernames():
        conn = pool.getconn()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT DISTINCT u.username
                    FROM run_metadata rm
                    JOIN users u ON rm.user_id = u.id
                    WHERE u.username IS NOT NULL
                    ORDER BY u.username
                """)
                return [row[0] for row in cur.fetchall()]
        finally:
            pool.putconn(conn)
    
    try:
        usernames = await asyncio.to_thread(_fetch_usernames)
        return {"usernames": usernames}
    except Exception as e:
        emit_log(f"[RUN_MANAGER] Failed to fetch usernames: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch usernames: {str(e)}")


@router.get("/workspaces")
async def list_workspaces(current_user: AdminUser):
    """
    Get list of all unique workspaces that have runs, including user info.
    Used for filter dropdown with client-side filtering by username.
    """
    pool = get_postgres_pool()
    
    def _fetch_workspaces():
        conn = pool.getconn()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT DISTINCT 
                        w.id, 
                        w.name,
                        u.username
                    FROM run_metadata rm
                    INNER JOIN workspaces w ON rm.workspace_id = w.id
                    LEFT JOIN users u ON w.user_id = u.id
                    WHERE rm.workspace_id IS NOT NULL
                    ORDER BY w.name, u.username
                """)
                return [
                    {
                        "id": str(row[0]), 
                        "name": row[1] or str(row[0]),
                        "username": row[2]
                    } 
                    for row in cur.fetchall()
                ]
        finally:
            pool.putconn(conn)
    
    try:
        workspaces = await asyncio.to_thread(_fetch_workspaces)
        return {"workspaces": workspaces}
    except Exception as e:
        emit_log(f"[RUN_MANAGER] Failed to fetch workspaces: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch workspaces: {str(e)}")
