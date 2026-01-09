"""
Skill Management API Endpoints

These endpoints allow CRUD operations on skills and hot-reload functionality.
"""

from fastapi import HTTPException
from pydantic import BaseModel
from typing import List, Dict, Any, Optional

# Get the API instance from main
from api.main import api

# --- SKILL MANAGEMENT ENDPOINTS ---

class SkillCreateRequest(BaseModel):
    name: str
    description: str
    requires: List[str] = []
    produces: List[str] = []
    optional_produces: List[str] = []
    executor: str = "llm"  # llm, rest, action
    hitl_enabled: bool = False
    prompt: Optional[str] = None
    system_prompt: Optional[str] = None
    rest_config: Optional[Dict[str, Any]] = None
    action_config: Optional[Dict[str, Any]] = None
    action_code: Optional[str] = None


class SkillUpdateRequest(BaseModel):
    description: Optional[str] = None
    requires: Optional[List[str]] = None
    produces: Optional[List[str]] = None
    optional_produces: Optional[List[str]] = None
    executor: Optional[str] = None
    hitl_enabled: Optional[bool] = None
    prompt: Optional[str] = None
    system_prompt: Optional[str] = None
    rest_config: Optional[Dict[str, Any]] = None
    action_config: Optional[Dict[str, Any]] = None
    action_code: Optional[str] = None


@api.get("/admin/skills")
async def list_skills():
    """Get all skills (filesystem + database) with metadata."""
    from skill_manager import get_all_skills_metadata
    
    try:
        skills = get_all_skills_metadata()
        return {"skills": skills, "count": len(skills)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to load skills: {str(e)}")


@api.get("/admin/skills/{skill_name}")
async def get_skill(skill_name: str):
    """Get detailed information about a specific skill."""
    from engine import SKILL_REGISTRY
    from skill_manager import get_db_connection
    
    skill = next((s for s in SKILL_REGISTRY if s.name == skill_name), None)
    if not skill:
        raise HTTPException(status_code=404, detail=f"Skill '{skill_name}' not found")
    
    # Check if skill exists in database to determine source
    source = "filesystem"
    db_metadata = {}
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT source, enabled, created_at, updated_at, action_code
                    FROM dynamic_skills
                    WHERE name = %s
                """, (skill_name,))
                row = cur.fetchone()
                if row:
                    source = row[0] or "database"
                    db_metadata = {
                        "enabled": row[1],
                        "created_at": row[2].isoformat() if row[2] else None,
                        "updated_at": row[3].isoformat() if row[3] else None,
                        "action_code": row[4],
                    }
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
async def create_skill(skill: SkillCreateRequest):
    """Create a new skill in the database."""
    from skill_manager import save_skill_to_database, reload_skill_registry
    
    try:
        skill_data = skill.dict()
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
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create skill: {str(e)}")


@api.put("/admin/skills/{skill_name}")
async def update_skill(skill_name: str, updates: SkillUpdateRequest):
    """Update an existing skill in the database."""
    from skill_manager import get_all_skills_metadata, save_skill_to_database, reload_skill_registry
    import psycopg
    from env_loader import load_env_once
    from pathlib import Path
    import os
    
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
    
    # Load current skill data from database
    load_env_once(Path(__file__).resolve().parents[1])
    db_uri = os.getenv("DATABASE_URL")
    
    try:
        with psycopg.connect(db_uri) as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT name, description, requires, produces, optional_produces,
                           executor, hitl_enabled, prompt, system_prompt,
                           rest_config, action_config, action_code
                    FROM dynamic_skills
                    WHERE name = %s
                """, (skill_name,))
                
                row = cur.fetchone()
                if not row:
                    raise HTTPException(status_code=404, detail=f"Skill '{skill_name}' not found in database")
                
                # Build updated skill data
                current_data = {
                    "name": row[0],
                    "description": row[1],
                    "requires": row[2] or [],
                    "produces": row[3] or [],
                    "optional_produces": row[4] or [],
                    "executor": row[5],
                    "hitl_enabled": row[6],
                    "prompt": row[7],
                    "system_prompt": row[8],
                    "rest_config": row[9],
                    "action_config": row[10],
                    "action_code": row[11],
                }
                
                # Apply updates
                update_dict = updates.dict(exclude_unset=True)
                current_data.update(update_dict)
                
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
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update skill: {str(e)}")


@api.delete("/admin/skills/{skill_name}")
async def delete_skill(skill_name: str):
    """Delete a skill from the database."""
    from skill_manager import delete_skill_from_database, reload_skill_registry, get_all_skills_metadata
    
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
async def reload_skills():
    """Reload all skills from filesystem and database (hot-reload)."""
    from skill_manager import reload_skill_registry
    
    try:
        count = reload_skill_registry()
        return {
            "status": "reloaded",
            "total_skills": count,
            "message": f"Successfully reloaded {count} skills"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to reload skills: {str(e)}")
