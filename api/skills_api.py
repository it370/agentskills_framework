"""
Skill Management API Endpoints

These endpoints allow CRUD operations on skills and hot-reload functionality.
"""

from fastapi import HTTPException
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
import ast

# Get the API instance from main
from api.main import api
from services.auth_middleware import AuthenticatedUser
from services.workspace_service import get_workspace_service


def validate_python_code(code: str, field_name: str = "code") -> None:
    """
    Validate Python code syntax by attempting to compile it.
    Raises HTTPException with clear error message if validation fails.
    """
    if not code or not code.strip():
        return  # Empty code is allowed
    
    try:
        ast.parse(code)
    except SyntaxError as e:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "Python syntax error",
                "field": field_name,
                "message": str(e.msg),
                "line": e.lineno,
                "offset": e.offset,
                "text": e.text.strip() if e.text else None,
                "hint": "Please fix the syntax error before saving. Common issues: missing colons, incorrect indentation, typos in keywords like 'def'"
            }
        )
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "Code validation failed",
                "field": field_name,
                "message": str(e),
                "hint": "Please ensure the code is valid Python"
            }
        )

# --- SKILL MANAGEMENT ENDPOINTS ---

class SkillCreateRequest(BaseModel):
    name: str
    description: str
    requires: List[str] = []
    produces: List[str] = []
    optional_produces: List[str] = []
    executor: str = "llm"  # llm, rest, action
    hitl_enabled: bool = False
    enabled: bool = True
    prompt: Optional[str] = None
    system_prompt: Optional[str] = None
    rest_config: Optional[Dict[str, Any]] = None
    action_config: Optional[Dict[str, Any]] = None
    action_code: Optional[str] = None
    action_functions: Optional[str] = None
    workspace_id: Optional[str] = None
    is_public: bool = False


class SkillUpdateRequest(BaseModel):
    description: Optional[str] = None
    requires: Optional[List[str]] = None
    produces: Optional[List[str]] = None
    optional_produces: Optional[List[str]] = None
    executor: Optional[str] = None
    hitl_enabled: Optional[bool] = None
    enabled: Optional[bool] = None
    prompt: Optional[str] = None
    system_prompt: Optional[str] = None
    rest_config: Optional[Dict[str, Any]] = None
    action_config: Optional[Dict[str, Any]] = None
    action_code: Optional[str] = None
    action_functions: Optional[str] = None
    is_public: Optional[bool] = None


@api.get("/admin/skills")
async def list_skills(current_user: AuthenticatedUser, workspace_id: Optional[str] = None):
    """Get skills visible in the current workspace (filesystem + public + owned)."""
    from skill_manager import get_all_skills_metadata
    
    try:
        workspace_service = get_workspace_service()
        workspace = await workspace_service.resolve_workspace(current_user.id, workspace_id)
        skills = get_all_skills_metadata()
        filtered = []
        for s in skills:
            source = s.get("source")
            skill_ws = s.get("workspace_id")
            is_public = s.get("is_public", False)
            if source == "filesystem":
                filtered.append(s)
            elif is_public or skill_ws == workspace.id:
                filtered.append(s)
        return {"skills": filtered, "count": len(filtered), "workspace_id": workspace.id}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to load skills: {str(e)}")


@api.get("/admin/skills/{skill_name}")
async def get_skill(skill_name: str, current_user: AuthenticatedUser, workspace_id: Optional[str] = None):
    """Get detailed information about a specific skill."""
    from engine import SKILL_REGISTRY, get_skill_registry_for_workspace
    from skill_manager import get_db_connection
    
    workspace_service = get_workspace_service()
    workspace = await workspace_service.resolve_workspace(current_user.id, workspace_id)
    
    # First check if skill is in the registry (enabled skills) and accessible
    registry = get_skill_registry_for_workspace(workspace.id)
    skill = next((s for s in registry if s.name == skill_name), None)
    
    # If not in registry, check database directly (could be disabled)
    if not skill:
        try:
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT name, module_name, description, requires, produces, optional_produces,
                               executor, hitl_enabled, prompt, system_prompt,
                               rest_config, action_config, action_code, action_functions,
                               source, enabled, created_at, updated_at,
                               workspace_id::text, owner_id::text, is_public
                        FROM dynamic_skills
                        WHERE name = %s
                    """, (skill_name,))
                    row = cur.fetchone()
                    
                    if not row:
                        raise HTTPException(status_code=404, detail=f"Skill '{skill_name}' not found")
                    
                    # Enforce workspace visibility
                    is_public = bool(row[20])
                    skill_workspace = row[18]
                    if not is_public and skill_workspace and skill_workspace != workspace.id:
                        raise HTTPException(status_code=404, detail=f"Skill '{skill_name}' not found")
                    
                    # Build skill dict from database row
                    skill_dict = {
                        "name": row[0],
                        "module_name": row[1],
                        "description": row[2],
                        "requires": row[3] or [],
                        "produces": row[4] or [],
                        "optional_produces": row[5] or [],
                        "executor": row[6],
                        "hitl_enabled": row[7],
                        "prompt": row[8],
                        "system_prompt": row[9],
                        "rest_config": row[10],
                        "action_config": row[11],
                        "action_code": row[12],
                        "action_functions": row[13],
                        "source": row[14] or "database",
                        "enabled": row[15],
                        "created_at": row[16].isoformat() if row[16] else None,
                        "updated_at": row[17].isoformat() if row[17] else None,
                        "workspace_id": skill_workspace,
                        "owner_id": row[19],
                        "is_public": is_public,
                    }
                    
                    return skill_dict
        except HTTPException:
            raise
        except Exception as e:
            print(f"[SKILLS_API] Error fetching skill from database: {e}")
            raise HTTPException(status_code=404, detail=f"Skill '{skill_name}' not found")
    
    # Skill found in registry - get additional metadata from database
    source = "filesystem"
    db_metadata = {}
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT source, enabled, created_at, updated_at, action_code, action_functions, module_name, workspace_id::text, owner_id::text, is_public
                    FROM dynamic_skills
                    WHERE name = %s
                """, (skill_name,))
                row = cur.fetchone()
                if row:
                    # Enforce workspace visibility
                    is_public = bool(row[9])
                    skill_workspace = row[7]
                    if not is_public and skill_workspace and skill_workspace != workspace.id:
                        raise HTTPException(status_code=404, detail=f"Skill '{skill_name}' not found")

                    source = row[0] or "database"
                    db_metadata = {
                        "enabled": row[1],
                        "created_at": row[2].isoformat() if row[2] else None,
                        "updated_at": row[3].isoformat() if row[3] else None,
                        "action_code": row[4],
                        "action_functions": row[5],
                        "module_name": row[6],
                        "workspace_id": skill_workspace,
                        "owner_id": row[8],
                        "is_public": is_public,
                    }
    except HTTPException:
        raise
    except Exception as e:
        print(f"[SKILLS_API] Warning: Failed to check database for skill source: {e}")
    
    # Convert to dict with all fields
    skill_dict = {
        "name": skill.name,
        "description": skill.description,
        "requires": list(skill.requires),
        "produces": list(skill.produces),
        "optional_produces": list(skill.optional_produces),
        "executor": skill.executor,
        "hitl_enabled": skill.hitl_enabled,
        "prompt": skill.prompt,
        "system_prompt": skill.system_prompt,
        "source": source,
        "workspace_id": getattr(skill, "workspace_id", None),
        "owner_id": getattr(skill, "owner_id", None),
        "is_public": getattr(skill, "is_public", False),
    }
    
    # Add database metadata if available
    if db_metadata:
        skill_dict.update(db_metadata)
    
    if skill.rest:
        skill_dict["rest_config"] = {
            "url": skill.rest.url,
            "method": skill.rest.method,
            "timeout": skill.rest.timeout,
            "headers": skill.rest.headers,
        }
    
    if skill.action:
        skill_dict["action_config"] = {
            "type": skill.action.type,
        }
        if skill.action.source:
            skill_dict["action_config"]["source"] = skill.action.source
        if skill.action.module:
            skill_dict["action_config"]["module"] = skill.action.module
        if skill.action.function:
            skill_dict["action_config"]["function"] = skill.action.function
        if skill.action.query:
            skill_dict["action_config"]["query"] = skill.action.query
        if skill.action.credential_ref:
            skill_dict["action_config"]["credential_ref"] = skill.action.credential_ref
    
    return skill_dict


@api.post("/admin/skills")
async def create_skill(skill: SkillCreateRequest, current_user: AuthenticatedUser):
    """Create a new skill in the database."""
    from skill_manager import save_skill_to_database, reload_skill_registry
    
    try:
        workspace_service = get_workspace_service()
        workspace = await workspace_service.resolve_workspace(current_user.id, skill.workspace_id)

        # Validate action_code if it's Python code (for action executor)
        if skill.action_code and skill.executor == "action":
            action_config = skill.action_config or {}
            action_type = action_config.get("type", "")
            
            # Validate inline Python code (not data_pipeline YAML)
            if action_type == "python":
                validate_python_code(skill.action_code, "action_code")
        
        # Validate action_functions (transform functions for data pipelines)
        if skill.action_functions:
            validate_python_code(skill.action_functions, "action_functions")
        
        skill_data = skill.dict()
        skill_data["workspace_id"] = workspace.id
        skill_data["owner_id"] = current_user.id
        skill_data["is_public"] = skill.is_public
        skill_id = save_skill_to_database(skill_data)
        
        # Reload registry to include new skill
        count = reload_skill_registry()
        
        return {
            "status": "created",
            "skill_id": skill_id,
            "name": skill.name,
            "total_skills": count,
            "message": f"Skill '{skill.name}' created and loaded successfully"
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create skill: {str(e)}")


@api.put("/admin/skills/{skill_name}")
async def update_skill(skill_name: str, updates: SkillUpdateRequest, current_user: AuthenticatedUser):
    """Update an existing skill in the database."""
    from skill_manager import get_all_skills_metadata, save_skill_to_database, reload_skill_registry
    import psycopg
    from env_loader import load_env_once
    from pathlib import Path
    import os
    
    workspace_service = get_workspace_service()
    
    # Check if skill exists and is from database
    all_skills = get_all_skills_metadata()
    skill_meta = next((s for s in all_skills if s["name"] == skill_name), None)
    
    if not skill_meta:
        raise HTTPException(status_code=404, detail=f"Skill '{skill_name}' not found")
    
    if skill_meta.get("source") != "database":
        raise HTTPException(
            status_code=400,
            detail=f"Cannot update filesystem skill '{skill_name}'. Only database skills can be updated via API."
        )

    # Ownership enforcement (unless admin)
    if not current_user.is_admin:
        owner_id = skill_meta.get("owner_id")
        if owner_id and owner_id != current_user.id:
            raise HTTPException(status_code=403, detail="Not authorized to update this skill")
    
    # Validate action_code if provided
    if updates.action_code is not None and updates.executor == "action":
        action_config = updates.action_config or {}
        action_type = action_config.get("type", "")
        
        # Validate inline Python code (not data_pipeline YAML)
        if action_type == "python":
            validate_python_code(updates.action_code, "action_code")
    
    # Validate action_functions if provided
    if updates.action_functions is not None:
        validate_python_code(updates.action_functions, "action_functions")
    
    # Load current skill data from database
    load_env_once(Path(__file__).resolve().parents[1])
    db_uri = os.getenv("DATABASE_URL")
    
    try:
        with psycopg.connect(db_uri) as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT name, module_name, description, requires, produces, optional_produces,
                           executor, hitl_enabled, prompt, system_prompt,
                           rest_config, action_config, action_code, action_functions,
                           workspace_id::text, owner_id::text, is_public
                    FROM dynamic_skills
                    WHERE name = %s
                """, (skill_name,))
                
                row = cur.fetchone()
                if not row:
                    raise HTTPException(status_code=404, detail=f"Skill '{skill_name}' not found in database")
                
                # Build updated skill data
                current_data = {
                    "name": row[0],
                    "module_name": row[1],
                    "description": row[2],
                    "requires": row[3] or [],
                    "produces": row[4] or [],
                    "optional_produces": row[5] or [],
                    "executor": row[6],
                    "hitl_enabled": row[7],
                    "prompt": row[8],
                    "system_prompt": row[9],
                    "rest_config": row[10],
                    "action_config": row[11],
                    "action_code": row[12],
                    "action_functions": row[13],
                    "workspace_id": row[14],
                    "owner_id": row[15],
                    "is_public": bool(row[16]),
                }

                # Determine workspace (immutable unless admin explicitly changes via request)
                target_workspace_id = (
                    updates.dict(exclude_unset=True).get("workspace_id")
                    or current_data.get("workspace_id")
                )
                if target_workspace_id:
                    workspace = await workspace_service.resolve_workspace(current_user.id, target_workspace_id)
                    current_data["workspace_id"] = workspace.id
                elif current_data.get("workspace_id"):
                    # Validate existing workspace ownership
                    await workspace_service.resolve_workspace(current_user.id, current_data["workspace_id"])
                else:
                    default_ws = await workspace_service.ensure_default(current_user.id)
                    current_data["workspace_id"] = default_ws.id
                current_data["owner_id"] = current_data.get("owner_id") or current_user.id
                
                # Apply updates
                update_dict = updates.dict(exclude_unset=True)
                current_data.update(update_dict)
                if updates.is_public is not None:
                    current_data["is_public"] = updates.is_public
                
                # Validate the final merged action_code and action_functions
                if current_data.get("action_code") and current_data.get("executor") == "action":
                    action_config = current_data.get("action_config") or {}
                    action_type = action_config.get("type", "")
                    if action_type == "python":
                        validate_python_code(current_data["action_code"], "action_code")
                
                if current_data.get("action_functions"):
                    validate_python_code(current_data["action_functions"], "action_functions")
                
                # Save back to database
                save_skill_to_database(current_data)
                
                # Reload registry
                count = reload_skill_registry()
                
                return {
                    "status": "updated",
                    "name": skill_name,
                    "total_skills": count,
                    "message": f"Skill '{skill_name}' updated and reloaded successfully"
                }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update skill: {str(e)}")


@api.delete("/admin/skills/{skill_name}")
async def delete_skill(skill_name: str, current_user: AuthenticatedUser):
    """Delete a skill from the database."""
    from skill_manager import delete_skill_from_database, reload_skill_registry, get_all_skills_metadata
    workspace_service = get_workspace_service()
    
    # Check if skill exists and is from database
    all_skills = get_all_skills_metadata()
    skill_meta = next((s for s in all_skills if s["name"] == skill_name), None)
    
    if not skill_meta:
        raise HTTPException(status_code=404, detail=f"Skill '{skill_name}' not found")
    
    if skill_meta.get("source") != "database":
        raise HTTPException(
            status_code=400,
            detail=f"Cannot delete filesystem skill '{skill_name}'. Only database skills can be deleted via API."
        )

    # Ownership enforcement (unless admin)
    if not current_user.is_admin:
        owner_id = skill_meta.get("owner_id")
        if owner_id and owner_id != current_user.id:
            raise HTTPException(status_code=403, detail="Not authorized to delete this skill")
    if skill_meta.get("workspace_id"):
        await workspace_service.resolve_workspace(current_user.id, skill_meta["workspace_id"])
    
    try:
        deleted = delete_skill_from_database(skill_name)
        if not deleted:
            raise HTTPException(status_code=404, detail=f"Skill '{skill_name}' not found in database")
        
        # Reload registry
        count = reload_skill_registry()
        
        return {
            "status": "deleted",
            "name": skill_name,
            "total_skills": count,
            "message": f"Skill '{skill_name}' deleted successfully"
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete skill: {str(e)}")


@api.post("/admin/skills/reload")
async def reload_skills(current_user: AuthenticatedUser, workspace_id: Optional[str] = None):
    """Reload skills for the current workspace (hot-reload)."""
    from skill_manager import reload_skill_registry
    
    try:
        workspace_service = get_workspace_service()
        workspace = await workspace_service.resolve_workspace(current_user.id, workspace_id)
        count = reload_skill_registry(workspace_id=workspace.id, include_public=True)
        return {
            "status": "reloaded",
            "total_skills": count,
            "workspace_id": workspace.id,
            "message": f"Successfully reloaded {count} skills for workspace {workspace.name}"
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to reload skills: {str(e)}")
