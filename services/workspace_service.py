"""
Workspace management service.

Provides:
- Per-user workspaces (isolated project areas)
- Default workspace handling
- Ownership validation helpers
"""

from __future__ import annotations

import asyncio
from typing import List, Optional
from datetime import datetime
from fastapi import HTTPException, status
from pydantic import BaseModel, Field, validator
import os
from services.connection_pool import get_postgres_pool


class Workspace(BaseModel):
    id: str
    user_id: str
    name: str
    code: str
    is_default: bool = False
    created_at: datetime
    updated_at: datetime


class WorkspaceCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=128)

    @validator("name")
    def trim_name(cls, v: str) -> str:
        cleaned = v.strip()
        if not cleaned:
            raise ValueError("Workspace name cannot be blank")
        return cleaned


class WorkspaceService:
    """Service for managing user workspaces using centralized connection pool"""
    
    def __init__(self):
        """Initialize WorkspaceService (uses centralized connection pool)"""
        pass

    async def ensure_default(self, user_id: str) -> Workspace:
        """
        Ensure the user has a default workspace and return it.
        """
        pool = get_postgres_pool()

        def _ensure():
            conn = pool.getconn()
            try:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT id::text, user_id::text, name, code, is_default, created_at, updated_at
                        FROM workspaces
                        WHERE user_id = %s AND is_default = TRUE
                        LIMIT 1
                        """,
                        (user_id,),
                    )
                    row = cur.fetchone()
                    if row:
                        return Workspace(
                            id=row[0],
                            user_id=row[1],
                            name=row[2],
                            code=row[3],
                            is_default=row[4],
                            created_at=row[5],
                            updated_at=row[6],
                        )

                    # Create a default workspace if none exist
                    cur.execute(
                        """
                        INSERT INTO workspaces (user_id, name, is_default)
                        VALUES (%s, 'default', TRUE)
                        ON CONFLICT (user_id, name) DO UPDATE SET is_default = TRUE
                        RETURNING id::text, user_id::text, name, code, is_default, created_at, updated_at
                        """,
                        (user_id,),
                    )
                    row = cur.fetchone()
                    conn.commit()
                    
                    return Workspace(
                        id=row[0],
                        user_id=row[1],
                        name=row[2],
                        code=row[3],
                        is_default=row[4],
                        created_at=row[5],
                        updated_at=row[6],
                    )
            finally:
                pool.putconn(conn)

        return await asyncio.to_thread(_ensure)

    async def list_workspaces(self, user_id: str) -> List[Workspace]:
        """List workspaces owned by the user (ensures default exists)."""
        await self.ensure_default(user_id)
        
        pool = get_postgres_pool()

        def _list():
            conn = pool.getconn()
            try:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT id::text, user_id::text, name, code, is_default, created_at, updated_at
                        FROM workspaces
                        WHERE user_id = %s
                        ORDER BY is_default DESC, name ASC
                        """,
                        (user_id,),
                    )
                    return [
                        Workspace(
                            id=row[0],
                            user_id=row[1],
                            name=row[2],
                            code=row[3],
                            is_default=row[4],
                            created_at=row[5],
                            updated_at=row[6],
                        )
                        for row in cur.fetchall()
                    ]
            finally:
                pool.putconn(conn)

        return await asyncio.to_thread(_list)

    async def create_workspace(self, user_id: str, name: str) -> Workspace:
        """Create a new workspace for the user."""
        create_req = WorkspaceCreate(name=name)
        
        pool = get_postgres_pool()

        def _create():
            conn = pool.getconn()
            try:
                with conn.cursor() as cur:
                    # If this is the first workspace, make it default
                    cur.execute("SELECT COUNT(*) FROM workspaces WHERE user_id = %s", (user_id,))
                    is_first = cur.fetchone()[0] == 0

                    cur.execute(
                        """
                        INSERT INTO workspaces (user_id, name, is_default)
                        VALUES (%s, %s, %s)
                        ON CONFLICT (user_id, name) DO NOTHING
                        RETURNING id::text, user_id::text, name, code, is_default, created_at, updated_at
                        """,
                        (user_id, create_req.name, is_first),
                    )
                    row = cur.fetchone()
                    if not row:
                        raise HTTPException(
                            status_code=status.HTTP_409_CONFLICT,
                            detail="Workspace name already exists",
                        )

                    if is_first and not row[3]:
                        # Force default flag if insert did not set it
                        cur.execute(
                            "UPDATE workspaces SET is_default = TRUE WHERE id = %s",
                            (row[0],),
                        )
                    
                    conn.commit()

                    return Workspace(
                        id=row[0],
                        user_id=row[1],
                        name=row[2],
                        code=row[3],
                        is_default=row[4] or is_first,
                        created_at=row[5],
                        updated_at=row[6],
                    )
            finally:
                pool.putconn(conn)

        return await asyncio.to_thread(_create)

    async def set_default(self, user_id: str, workspace_id: str) -> Workspace:
        """Mark a workspace as default for the user."""
        
        pool = get_postgres_pool()

        def _set_default():
            conn = pool.getconn()
            try:
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT user_id::text FROM workspaces WHERE id = %s",
                        (workspace_id,),
                    )
                    row = cur.fetchone()
                    if not row:
                        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found")
                    if row[0] != user_id:
                        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your workspace")

                    cur.execute(
                        "UPDATE workspaces SET is_default = FALSE WHERE user_id = %s AND id != %s",
                        (user_id, workspace_id),
                    )
                    cur.execute(
                        """
                        UPDATE workspaces
                        SET is_default = TRUE, updated_at = NOW()
                        WHERE id = %s
                        RETURNING id::text, user_id::text, name, code, is_default, created_at, updated_at
                        """,
                        (workspace_id,),
                    )
                    row = cur.fetchone()
                    conn.commit()
                    
                    return Workspace(
                        id=row[0],
                        user_id=row[1],
                        name=row[2],
                        code=row[3],
                        is_default=row[4],
                        created_at=row[5],
                        updated_at=row[6],
                    )
            finally:
                pool.putconn(conn)

        return await asyncio.to_thread(_set_default)

    async def resolve_workspace(self, user_id: str, workspace_id: Optional[str]) -> Workspace:
        """
        Resolve a workspace for the user:
        - If workspace_id is provided, validate ownership
        - Otherwise return default workspace
        """
        if not workspace_id:
            return await self.ensure_default(user_id)
        
        pool = get_postgres_pool()

        def _resolve():
            conn = pool.getconn()
            try:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT id::text, user_id::text, name, code, is_default, created_at, updated_at
                        FROM workspaces
                        WHERE id = %s
                        """,
                        (workspace_id,),
                    )
                    row = cur.fetchone()
                    if not row:
                        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found")
                    if row[1] != user_id:
                        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your workspace")
                    return Workspace(
                        id=row[0],
                        user_id=row[1],
                        name=row[2],
                        code=row[3],
                        is_default=row[4],
                        created_at=row[5],
                        updated_at=row[6],
                    )
            finally:
                pool.putconn(conn)

        return await asyncio.to_thread(_resolve)


_workspace_service: Optional[WorkspaceService] = None


def get_workspace_service() -> WorkspaceService:
    """Get global workspace service instance."""
    global _workspace_service
    if _workspace_service is None:
        _workspace_service = WorkspaceService()
    return _workspace_service
