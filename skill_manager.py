"""
Dynamic Skill Management

Handles loading, saving, and reloading skills from both filesystem and database.
Supports hot-reload without application restart.
"""

import os
import json
from typing import List, Dict, Any, Optional
from pathlib import Path
import psycopg
from pydantic import ValidationError

from env_loader import load_env_once


def get_db_connection():
    """Get database connection using environment settings."""
    load_env_once(Path(__file__).resolve().parent)
    db_uri = os.getenv("DATABASE_URL")
    if not db_uri:
        raise RuntimeError("DATABASE_URL not configured")
    return psycopg.connect(db_uri)


def load_skills_from_database() -> List[Dict[str, Any]]:
    """
    Load all enabled skills from the database.
    
    Returns:
        List of skill dictionaries compatible with Skill model
        
    Note: Skills with errors are skipped and logged, but do not prevent other skills from loading.
    """
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT 
                        name, description, requires, produces, optional_produces,
                        executor, hitl_enabled, prompt, system_prompt,
                        rest_config, action_config, action_code, action_functions
                    FROM dynamic_skills
                    WHERE enabled = true
                    ORDER BY name
                """)
                
                skills = []
                for row in cur.fetchall():
                    (name, description, requires, produces, optional_produces,
                     executor, hitl_enabled, prompt, system_prompt,
                     rest_config, action_config, action_code, action_functions) = row
                    
                    try:
                        skill_dict = {
                            "name": name,
                            "description": description,
                            "requires": set(requires or []),
                            "produces": set(produces or []),
                            "optional_produces": set(optional_produces or []),
                            "executor": executor,
                            "hitl_enabled": hitl_enabled,
                            "prompt": prompt,
                            "system_prompt": system_prompt,
                        }
                        
                        # Add executor-specific config
                        if executor == "rest" and rest_config:
                            from engine import ActionConfig
                            skill_dict["rest"] = RestConfig(**rest_config)
                        elif executor == "action" and action_config:
                            from engine import ActionConfig
                            import yaml
                            
                            # For data_pipeline, parse steps from action_code YAML
                            if action_config.get("type") == "data_pipeline" and action_code:
                                try:
                                    # Parse YAML from action_code
                                    pipeline_data = yaml.safe_load(action_code)
                                    if pipeline_data and "steps" in pipeline_data:
                                        action_config["steps"] = pipeline_data["steps"]
                                    else:
                                        print(f"[SKILL_DB] Warning: No 'steps' found in pipeline YAML for {name}")
                                except Exception as e:
                                    print(f"[SKILL_DB] Warning: Failed to parse pipeline YAML for {name}: {e}")
                                    # Continue without pipeline steps - skill will fail at runtime but won't crash loading
                                
                                # Register pipeline functions if provided
                                if action_functions:
                                    try:
                                        _register_pipeline_functions(name, action_functions)
                                    except (SyntaxError, RuntimeError) as e:
                                        print(f"[SKILL_DB] ERROR: Skipping skill '{name}' due to invalid pipeline functions: {e}")
                                        # Skip this skill entirely - bad Python code should not be registered
                                        continue
                            
                            skill_dict["action"] = ActionConfig(**action_config)

                            # If python_function with inline code, save to temp file and register
                            if action_config.get("type") == "python_function" and action_code:
                                try:
                                    _register_inline_action(name, action_config["function"], action_code)
                                except Exception as e:
                                    print(f"[SKILL_DB] ERROR: Skipping skill '{name}' due to invalid action code: {e}")
                                    continue
                        
                        skills.append(skill_dict)
                        
                    except Exception as e:
                        # Log the error but continue loading other skills
                        print(f"[SKILL_DB] ERROR: Failed to load skill '{name}': {e}")
                        print(f"[SKILL_DB] Skipping skill '{name}' - other skills will continue to load")
                        continue
                
                print(f"[SKILL_DB] Successfully loaded {len(skills)} skills from database")
                return skills
    except Exception as e:
        print(f"[SKILL_DB] Warning: Failed to load skills from database: {e}")
        return []


def _register_inline_action(skill_name: str, function_name: str, code: str):
    """
    Register a Python function from inline code for action execution.
    
    Creates a temporary module and registers the function in ACTION_REGISTRY.
    """
    import sys
    import types
    from actions import ACTION_REGISTRY
    
    # Create a module for this skill's action
    module_name = f"dynamic_skills.{skill_name}"
    module = types.ModuleType(module_name)
    module.__file__ = f"<dynamic:{skill_name}>"
    
    # Execute the code in the module's namespace
    try:
        exec(code, module.__dict__)
        
        # Get the function from the module
        if not hasattr(module, function_name):
            raise RuntimeError(f"Function '{function_name}' not found in action code")
        
        func = getattr(module, function_name)
        
        # Register in ACTION_REGISTRY
        registry_key = f"{module_name}.{function_name}"
        ACTION_REGISTRY[registry_key] = func
        
        # Also add module to sys.modules for imports
        sys.modules[module_name] = module
        
        print(f"[SKILL_DB] Registered inline action: {registry_key}")
        
    except Exception as e:
        raise RuntimeError(f"Failed to register inline action for {skill_name}: {e}")


def _register_pipeline_functions(skill_name: str, functions_code: str):
    """
    Register Python functions for data_pipeline transform steps.
    
    Registers all functions defined in the code into the _ACTION_FUNCTION_REGISTRY.
    
    Raises:
        SyntaxError: If the Python code has syntax errors
        RuntimeError: If the code cannot be executed
    """
    import sys
    import types
    from engine import _ACTION_FUNCTION_REGISTRY
    
    # Create a module for this skill's pipeline functions
    module_name = f"pipeline_functions.{skill_name}"
    module = types.ModuleType(module_name)
    module.__file__ = f"<pipeline:{skill_name}>"
    
    # Execute the code in the module's namespace
    try:
        # First, validate syntax by compiling (this gives better error messages)
        compile(functions_code, f"<pipeline:{skill_name}>", 'exec')
        
        # If compilation succeeds, execute it
        exec(functions_code, module.__dict__)
        
        # Find all callable functions defined in the module (exclude built-ins)
        registered_count = 0
        for attr_name in dir(module):
            if not attr_name.startswith('_'):  # Skip private/magic methods
                attr = getattr(module, attr_name)
                if callable(attr) and hasattr(attr, '__module__'):
                    # Register the function
                    _ACTION_FUNCTION_REGISTRY[attr_name] = attr
                    registered_count += 1
        
        # Also add module to sys.modules for imports
        sys.modules[module_name] = module
        
        print(f"[SKILL_DB] Registered {registered_count} pipeline functions for {skill_name}")
        
    except SyntaxError as e:
        # Provide detailed syntax error information
        error_msg = f"Syntax error in pipeline functions: {e.msg}"
        if e.lineno:
            error_msg += f" (line {e.lineno}"
            if e.offset:
                error_msg += f", column {e.offset}"
            error_msg += ")"
        if e.text:
            error_msg += f"\n  → {e.text.strip()}"
        raise SyntaxError(error_msg)
    except Exception as e:
        raise RuntimeError(f"Failed to register pipeline functions for {skill_name}: {e}")


def save_skill_to_database(skill_data: Dict[str, Any]) -> int:
    """
    Save or update a skill in the database.
    
    Args:
        skill_data: Skill configuration dictionary
        
    Returns:
        Skill ID (int)
    """
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO dynamic_skills (
                    name, description, requires, produces, optional_produces,
                    executor, hitl_enabled, prompt, system_prompt,
                    rest_config, action_config, action_code, action_functions, source
                ) VALUES (
                    %(name)s, %(description)s, %(requires)s, %(produces)s, %(optional_produces)s,
                    %(executor)s, %(hitl_enabled)s, %(prompt)s, %(system_prompt)s,
                    %(rest_config)s, %(action_config)s, %(action_code)s, %(action_functions)s, 'database'
                )
                ON CONFLICT (name) DO UPDATE SET
                    description = EXCLUDED.description,
                    requires = EXCLUDED.requires,
                    produces = EXCLUDED.produces,
                    optional_produces = EXCLUDED.optional_produces,
                    executor = EXCLUDED.executor,
                    hitl_enabled = EXCLUDED.hitl_enabled,
                    prompt = EXCLUDED.prompt,
                    system_prompt = EXCLUDED.system_prompt,
                    rest_config = EXCLUDED.rest_config,
                    action_config = EXCLUDED.action_config,
                    action_code = EXCLUDED.action_code,
                    action_functions = EXCLUDED.action_functions
                RETURNING id
            """, {
                "name": skill_data["name"],
                "description": skill_data.get("description", ""),
                "requires": json.dumps(list(skill_data.get("requires", []))),
                "produces": json.dumps(list(skill_data.get("produces", []))),
                "optional_produces": json.dumps(list(skill_data.get("optional_produces", []))),
                "executor": skill_data.get("executor", "llm"),
                "hitl_enabled": skill_data.get("hitl_enabled", False),
                "prompt": skill_data.get("prompt"),
                "system_prompt": skill_data.get("system_prompt"),
                "rest_config": json.dumps(skill_data.get("rest_config")) if skill_data.get("rest_config") else None,
                "action_config": json.dumps(skill_data.get("action_config")) if skill_data.get("action_config") else None,
                "action_code": skill_data.get("action_code"),
                "action_functions": skill_data.get("action_functions"),
            })
            
            skill_id = cur.fetchone()[0]
            conn.commit()
            return skill_id


def delete_skill_from_database(skill_name: str) -> bool:
    """
    Delete a skill from the database.
    
    Args:
        skill_name: Name of skill to delete
        
    Returns:
        True if deleted, False if not found
    """
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM dynamic_skills WHERE name = %s RETURNING id", (skill_name,))
            result = cur.fetchone()
            conn.commit()
            return result is not None


def get_all_skills_metadata() -> List[Dict[str, Any]]:
    """
    Get metadata for all skills (filesystem + database) without loading full configs.
    
    Returns:
        List of skill metadata dicts with name, description, source, etc.
    """
    skills = []
    
    # Get database skills
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT name, description, executor, enabled, created_at, updated_at, source, action_config
                    FROM dynamic_skills
                    ORDER BY name
                """)
                for row in cur.fetchall():
                    skills.append({
                        "name": row[0],
                        "description": row[1],
                        "executor": row[2],
                        "enabled": row[3],
                        "created_at": row[4].isoformat() if row[4] else None,
                        "updated_at": row[5].isoformat() if row[5] else None,
                        "source": row[6],
                        "action_config": row[7],  # Add action_config
                    })
    except Exception as e:
        print(f"[SKILL_DB] Warning: Failed to get database skills: {e}")
    
    # Get filesystem skills
    try:
        skills_dir = Path(__file__).parent / "skills"
        if skills_dir.exists():
            for entry in skills_dir.iterdir():
                if entry.is_dir():
                    skill_md = entry / "skill.md"
                    if skill_md.exists():
                        # Quick parse just for metadata - read YAML frontmatter manually
                        try:
                            with open(skill_md, 'r', encoding='utf-8') as f:
                                content = f.read()
                                # Simple YAML frontmatter extraction
                                if content.startswith('---'):
                                    parts = content.split('---', 2)
                                    if len(parts) >= 2:
                                        import yaml
                                        meta = yaml.safe_load(parts[1])
                                        skill_data = {
                                            "name": meta.get("name", entry.name),
                                            "description": meta.get("description", ""),
                                            "executor": meta.get("executor", "llm"),
                                            "enabled": True,
                                            "source": "filesystem",
                                            "path": str(skill_md),
                                        }
                                        # Add action_config if present
                                        if meta.get("action"):
                                            skill_data["action_config"] = meta["action"]
                                        skills.append(skill_data)
                        except Exception as e:
                            print(f"[SKILL_DB] Warning: Failed to parse {skill_md}: {e}")
    except Exception as e:
        print(f"[SKILL_DB] Warning: Failed to get filesystem skills: {e}")
    
    return skills


def reload_skill_registry():
    """
    Reload the skill registry from both filesystem and database.
    
    This allows hot-reload without restarting the application.
    """
    from engine import load_skill_registry, Skill
    import engine
    
    # Load from filesystem
    filesystem_skills = load_skill_registry()
    
    # Load from database
    db_skill_dicts = load_skills_from_database()
    db_skills = []
    for skill_dict in db_skill_dicts:
        try:
            skill = Skill(**skill_dict)
            db_skills.append(skill)
        except ValidationError as e:
            print(f"[SKILL_DB] Warning: Invalid skill '{skill_dict.get('name')}': {e}")
    
    # Combine (database skills override filesystem if name conflicts)
    skill_map = {s.name: s for s in filesystem_skills}
    for db_skill in db_skills:
        skill_map[db_skill.name] = db_skill  # Database takes precedence
    
    # Update global registry
    engine.SKILL_REGISTRY = list(skill_map.values())
    
    print(f"[SKILL_DB] Reloaded {len(engine.SKILL_REGISTRY)} skills ({len(filesystem_skills)} from files, {len(db_skills)} from database)")
    
    return len(engine.SKILL_REGISTRY)
