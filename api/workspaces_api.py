"""
Workspace management endpoints.

Scopes skills and runs per user workspace and supports switching with skill re-registration.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from services.auth_middleware import AuthenticatedUser
from services.workspace_service import get_workspace_service
from skill_manager import reload_skill_registry


router = APIRouter(prefix="/workspaces", tags=["Workspaces"])


class WorkspaceCreateRequest(BaseModel):
    name: str
    make_default: bool = False


class WorkspaceSwitchRequest(BaseModel):
    workspace_id: str
    set_default: bool = True


@router.get("")
async def list_workspaces(current_user: AuthenticatedUser):
    """List workspaces for the authenticated user (ensures default exists)."""
    service = get_workspace_service()
    workspaces = await service.list_workspaces(current_user.id)
    default_ws = next((ws for ws in workspaces if ws.is_default), None)
    return {
        "workspaces": [ws.dict() for ws in workspaces],
        "default_workspace_id": default_ws.id if default_ws else None,
    }


@router.post("")
async def create_workspace(req: WorkspaceCreateRequest, current_user: AuthenticatedUser):
    """Create a new workspace for the current user."""
    service = get_workspace_service()
    workspace = await service.create_workspace(current_user.id, req.name)
    if req.make_default:
        workspace = await service.set_default(current_user.id, workspace.id)
    return {"workspace": workspace.dict()}


@router.post("/switch")
async def switch_workspace(req: WorkspaceSwitchRequest, current_user: AuthenticatedUser):
    """
    Switch active workspace (validates ownership) and reload skills for that scope.
    """
    service = get_workspace_service()
    target = await service.resolve_workspace(current_user.id, req.workspace_id)
    if req.set_default:
        target = await service.set_default(current_user.id, target.id)

    # Re-register skills (reload all and rely on workspace filters at runtime)
    skills_count = reload_skill_registry()

    return {"workspace": target.dict(), "skills_loaded": skills_count}
