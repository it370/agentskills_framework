"""
Skill Management API Endpoints

These endpoints allow CRUD operations on skills and hot-reload functionality.
"""

from fastapi import HTTPException
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
import ast
import json

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
    llm_model: Optional[str] = None
    rest_config: Optional[Dict[str, Any]] = None
    action_config: Optional[Dict[str, Any]] = None
    action_code: Optional[str] = None
    action_functions: Optional[str] = None
    workspace_id: Optional[str] = None
    is_public: bool = False


class SkillUpdateRequest(BaseModel):
    """Request model for updating a skill. Note: name cannot be changed after creation."""
    name: Optional[str] = None  # Will be rejected if provided
    description: Optional[str] = None
    requires: Optional[List[str]] = None
    produces: Optional[List[str]] = None
    optional_produces: Optional[List[str]] = None
    executor: Optional[str] = None
    hitl_enabled: Optional[bool] = None
    enabled: Optional[bool] = None
    prompt: Optional[str] = None
    system_prompt: Optional[str] = None
    llm_model: Optional[str] = None
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


@api.get("/admin/skills/{skill_identifier}")
async def get_skill(skill_identifier: str, current_user: AuthenticatedUser, workspace_id: Optional[str] = None):
    """Get detailed information about a specific skill by ID or name."""
    from engine import SKILL_REGISTRY, get_skill_registry_for_workspace
    from skill_manager import get_db_connection
    import uuid
    
    workspace_service = get_workspace_service()
    workspace = await workspace_service.resolve_workspace(current_user.id, workspace_id)
    
    # Determine if identifier is a UUID (ID) or a name
    is_uuid = False
    try:
        uuid.UUID(skill_identifier)
        is_uuid = True
    except (ValueError, AttributeError):
        is_uuid = False
    
    # First check if skill is in the registry (enabled skills) and accessible
    # Registry only has names, so if it's a UUID we need to look up in DB first
    skill = None
    skill_name_for_registry = None
    
    if not is_uuid:
        # It's a name, check registry directly
        registry = get_skill_registry_for_workspace(workspace.id)
        skill = next((s for s in registry if s.name == skill_identifier), None)
        skill_name_for_registry = skill_identifier
    
    # If not in registry or is UUID, check database directly (could be disabled or need name lookup)
    if not skill:
        try:
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    if is_uuid:
                        # Look up by ID
                        cur.execute("""
                            SELECT id::text, name, module_name, description, requires, produces, optional_produces,
                                   executor, hitl_enabled, prompt, system_prompt, llm_model,
                                   rest_config, action_config, action_code, action_functions,
                                   source, enabled, created_at, updated_at,
                                   workspace_id::text, owner_id::text, is_public
                            FROM dynamic_skills
                            WHERE id = %s
                        """, (skill_identifier,))
                    else:
                        # Look up by name
                        cur.execute("""
                            SELECT id::text, name, module_name, description, requires, produces, optional_produces,
                                   executor, hitl_enabled, prompt, system_prompt, llm_model,
                                   rest_config, action_config, action_code, action_functions,
                                   source, enabled, created_at, updated_at,
                                   workspace_id::text, owner_id::text, is_public
                            FROM dynamic_skills
                            WHERE name = %s
                        """, (skill_identifier,))
                    
                    row = cur.fetchone()
                    
                    if not row:
                        raise HTTPException(status_code=404, detail=f"Skill not found")
                    
                    # Enforce workspace visibility
                    is_public = bool(row[22])
                    skill_workspace = row[20]
                    if not is_public and skill_workspace and skill_workspace != workspace.id:
                        raise HTTPException(status_code=404, detail=f"Skill not found")
                    
                    # Build skill dict from database row
                    skill_dict = {
                        "id": row[0],
                        "name": row[1],
                        "module_name": row[2],
                        "description": row[3],
                        "requires": row[4] or [],
                        "produces": row[5] or [],
                        "optional_produces": row[6] or [],
                        "executor": row[7],
                        "hitl_enabled": row[8],
                        "prompt": row[9],
                        "system_prompt": row[10],
                        "llm_model": row[11],
                        "rest_config": row[12],
                        "action_config": row[13],
                        "action_code": row[14],
                        "action_functions": row[15],
                        "source": row[16] or "database",
                        "enabled": row[17],
                        "created_at": row[18].isoformat() if row[18] else None,
                        "updated_at": row[19].isoformat() if row[19] else None,
                        "workspace_id": skill_workspace,
                        "owner_id": row[21],
                        "is_public": is_public,
                    }
                    
                    return skill_dict
        except HTTPException:
            raise
        except Exception as e:
            print(f"[SKILLS_API] Error fetching skill from database: {e}")
            raise HTTPException(status_code=404, detail=f"Skill not found")
    
    # Skill found in registry - get additional metadata from database if it's a database skill
    source = "filesystem"
    db_metadata = {}
    
    # For registry skills, get the name for DB lookup
    if skill:
        skill_name_for_registry = skill.name
    
    if skill_name_for_registry:
        try:
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT id::text, source, enabled, created_at, updated_at, action_code, action_functions, module_name, workspace_id::text, owner_id::text, is_public
                        FROM dynamic_skills
                        WHERE name = %s
                    """, (skill_name_for_registry,))
                    row = cur.fetchone()
                    if row:
                        # Enforce workspace visibility
                        is_public = bool(row[10])
                        skill_workspace = row[8]
                        if not is_public and skill_workspace and skill_workspace != workspace.id:
                            raise HTTPException(status_code=404, detail=f"Skill not found")

                        source = row[1] or "database"
                        db_metadata = {
                            "id": row[0],
                            "enabled": row[2],
                            "created_at": row[3].isoformat() if row[3] else None,
                            "updated_at": row[4].isoformat() if row[4] else None,
                            "action_code": row[5],
                            "action_functions": row[6],
                            "module_name": row[7],
                            "workspace_id": skill_workspace,
                            "owner_id": row[9],
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
        "llm_model": getattr(skill, "llm_model", None),
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
    import psycopg
    
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
    except psycopg.errors.UniqueViolation as e:
        # Handle duplicate skill name or module name
        error_msg = str(e)
        if "workspace_name" in error_msg or "unique_module_name" in error_msg or "module_name" in error_msg:
            raise HTTPException(
                status_code=409,
                detail=f"A skill with the name '{skill.name}' already exists in this workspace. Skill names must be unique within a workspace."
            )
        else:
            raise HTTPException(status_code=409, detail=f"This skill conflicts with an existing skill: {error_msg}")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create skill: {str(e)}")


@api.put("/admin/skills/{skill_id}")
async def update_skill(skill_id: str, updates: SkillUpdateRequest, current_user: AuthenticatedUser):
    """Update an existing skill in the database by ID."""
    from skill_manager import save_skill_to_database, reload_skill_registry
    import psycopg
    from env_loader import load_env_once
    from pathlib import Path
    import os
    
    workspace_service = get_workspace_service()
    
    # STRICT: Prevent name changes during update
    if updates.name is not None:
        raise HTTPException(
            status_code=400,
            detail="Skill name cannot be changed after creation. Delete and recreate the skill if you need a different name."
        )
    
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
                           executor, hitl_enabled, prompt, system_prompt, llm_model,
                           rest_config, action_config, action_code, action_functions,
                           workspace_id::text, owner_id::text, is_public, source
                    FROM dynamic_skills
                    WHERE id = %s
                """, (skill_id,))
                
                row = cur.fetchone()
                if not row:
                    raise HTTPException(status_code=404, detail=f"Skill not found")
                
                # Build current skill data
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
                    "llm_model": row[10],
                    "rest_config": row[11],
                    "action_config": row[12],
                    "action_code": row[13],
                    "action_functions": row[14],
                    "workspace_id": row[15],
                    "owner_id": row[16],
                    "is_public": bool(row[17]),
                    "source": row[18],
                }
                
                # Verify it's a database skill
                if current_data.get("source") != "database":
                    raise HTTPException(
                        status_code=400,
                        detail=f"Cannot update filesystem skill. Only database skills can be updated via API."
                    )
                
                # Ownership enforcement (unless admin)
                if not current_user.is_admin:
                    owner_id = current_data.get("owner_id")
                    if owner_id and owner_id != current_user.id:
                        raise HTTPException(status_code=403, detail="Not authorized to update this skill")
                
                # Workspace verification
                if current_data.get("workspace_id"):
                    await workspace_service.resolve_workspace(current_user.id, current_data["workspace_id"])
                
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
                
                # Add the ID to enable ID-based update in save_skill_to_database
                current_data["id"] = skill_id
                
                # Save back to database using save_skill_to_database (with ID = UPDATE mode)
                returned_id = save_skill_to_database(current_data)
                
                # Reload registry
                count = reload_skill_registry()
                
                return {
                    "status": "updated",
                    "skill_id": returned_id,
                    "name": current_data["name"],
                    "total_skills": count,
                    "message": f"Skill '{current_data['name']}' updated and reloaded successfully"
                }
    except psycopg.errors.UniqueViolation as e:
        # Handle duplicate skill name when renaming
        error_msg = str(e)
        skill_name = current_data.get("name", "this skill") if 'current_data' in locals() else "this skill"
        if "workspace_name" in error_msg or "unique_module_name" in error_msg or "module_name" in error_msg:
            raise HTTPException(
                status_code=409,
                detail=f"A skill with the name '{skill_name}' already exists in this workspace. Skill names must be unique within a workspace."
            )
        else:
            raise HTTPException(status_code=409, detail=f"This skill update conflicts with an existing skill: {error_msg}")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update skill: {str(e)}")


@api.delete("/admin/skills/{skill_id}")
async def delete_skill(skill_id: str, current_user: AuthenticatedUser):
    """Delete a skill from the database by ID."""
    from skill_manager import reload_skill_registry
    import psycopg
    from env_loader import load_env_once
    from pathlib import Path
    import os
    
    workspace_service = get_workspace_service()
    
    # Load environment
    load_env_once(Path(__file__).resolve().parents[1])
    db_uri = os.getenv("DATABASE_URL")
    
    try:
        with psycopg.connect(db_uri) as conn:
            with conn.cursor() as cur:
                # Get skill details
                cur.execute("""
                    SELECT name, source, owner_id::text, workspace_id::text
                    FROM dynamic_skills
                    WHERE id = %s
                """, (skill_id,))
                
                row = cur.fetchone()
                if not row:
                    raise HTTPException(status_code=404, detail=f"Skill not found")
                
                skill_name, source, owner_id, workspace_id = row
                
                # Verify it's a database skill
                if source != "database":
                    raise HTTPException(
                        status_code=400,
                        detail=f"Cannot delete filesystem skill '{skill_name}'. Only database skills can be deleted via API."
                    )
                
                # Ownership enforcement (unless admin)
                if not current_user.is_admin:
                    if owner_id and owner_id != current_user.id:
                        raise HTTPException(status_code=403, detail="Not authorized to delete this skill")
                
                # Workspace verification
                if workspace_id:
                    await workspace_service.resolve_workspace(current_user.id, workspace_id)
                
                # Delete the skill by ID
                cur.execute("DELETE FROM dynamic_skills WHERE id = %s RETURNING name", (skill_id,))
                result = cur.fetchone()
                if not result:
                    raise HTTPException(status_code=404, detail=f"Skill not found")
                
                deleted_name = result[0]
                conn.commit()
        
        # Reload registry
        count = reload_skill_registry()
        
        return {
            "status": "deleted",
            "skill_id": skill_id,
            "name": deleted_name,
            "total_skills": count,
            "message": f"Skill '{deleted_name}' deleted successfully"
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
