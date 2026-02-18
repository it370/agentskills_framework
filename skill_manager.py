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


def load_skills_from_database(workspace_id: Optional[str] = None, include_public: bool = True) -> List[Dict[str, Any]]:
    """
    Load all enabled skills from the database.
    
    Returns:
        List of skill dictionaries compatible with Skill model
        
    Note: Skills with errors are skipped and logged, but do not prevent other skills from loading.
    """
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                base_sql = """
                    SELECT 
                        name,
                        module_name,
                        description,
                        requires,
                        produces,
                        optional_produces,
                        executor,
                        hitl_enabled,
                        prompt,
                        system_prompt,
                        llm_model,
                        rest_config,
                        action_config,
                        action_code,
                        action_functions,
                        workspace_id::text,
                        owner_id::text,
                        is_public
                    FROM dynamic_skills
                    WHERE enabled = true
                """
                params: list[Any] = []
                if workspace_id:
                    # Restrict to workspace or public skills
                    base_sql += " AND (workspace_id = %s"
                    params.append(workspace_id)
                    if include_public:
                        base_sql += " OR is_public = TRUE"
                    base_sql += ")"
                elif not include_public:
                    # If caller explicitly disables public skills, still filter on enabled
                    base_sql += " AND false"  # No skills returned (safety guard)
                base_sql += " ORDER BY name"
                cur.execute(base_sql, params)
                
                skills = []
                for row in cur.fetchall():
                    (name, module_name, description, requires, produces, optional_produces,
                     executor, hitl_enabled, prompt, system_prompt, llm_model,
                     rest_config, action_config, action_code, action_functions,
                     workspace_id, owner_id, is_public) = row
                    
                    try:
                        skill_dict = {
                            "name": name,
                            "module_name": module_name,
                            "description": description,
                            "requires": set(requires or []),
                            "produces": set(produces or []),
                            "optional_produces": set(optional_produces or []),
                            "executor": executor,
                            "hitl_enabled": hitl_enabled,
                            "prompt": prompt,
                            "system_prompt": system_prompt,
                            "llm_model": llm_model,
                            "workspace_id": workspace_id,
                            "owner_id": owner_id,
                            "is_public": bool(is_public),
                        }
                        
                        # Add executor-specific config
                        if executor == "rest" and rest_config:
                            from engine import RestConfig
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
                                
                                # Register pipeline functions if provided (but don't fail skill loading)
                                if action_functions:
                                    try:
                                        _register_pipeline_functions(module_name, action_functions)
                                    except (SyntaxError, RuntimeError) as e:
                                        print(f"[SKILL_DB] WARNING: Failed to register pipeline functions for '{name}': {e}")
                                        print(f"[SKILL_DB] Skill '{name}' will still load but pipeline may fail at runtime")
                                        # Don't skip the skill - allow it to load so it can be edited
                            
                            # If python_function with inline code, register and update module path
                            if action_config.get("type") == "python_function" and action_code:
                                try:
                                    # Check if function name is specified
                                    function_name = action_config.get("function")
                                    if not function_name:
                                        raise ValueError("action_config must include 'function' field specifying the function name to call")
                                    
                                    # Register the function with the module_name
                                    _register_inline_action(module_name, function_name, action_code)
                                    
                                    # Update action_config to use correct module path BEFORE creating ActionConfig
                                    action_config["module"] = f"dynamic_skills.{module_name}"
                                except Exception as e:
                                    print(f"[SKILL_DB] WARNING: Failed to register action code for '{name}': {e}")
                                    print(f"[SKILL_DB] Skill '{name}' will still load but may fail at runtime")
                                    # Don't skip the skill - allow it to load so it can be edited
                            
                            # Create ActionConfig AFTER updating the module field
                            skill_dict["action"] = ActionConfig(**action_config)
                        
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


def _register_inline_action(module_name: str, function_name: str, code: str):
    """
    Register a Python function from inline code for action execution.
    
    Creates a temporary module and registers the function in ACTION_REGISTRY.
    
    Args:
        module_name: The Python module name (from module_name column, already sanitized)
        function_name: The function name to register
        code: The Python code containing the function
    """
    import sys
    import types
    from actions import ACTION_REGISTRY

    def _ensure_virtual_packages(full_name: str) -> None:
        """
        Ensure all parent packages exist in sys.modules for dotted module paths.
        Example: for 'dynamic_skills.abcd1234.foo', ensure:
          - dynamic_skills (package)
          - dynamic_skills.abcd1234 (package)
        """
        parts = full_name.split(".")
        for i in range(1, len(parts)):
            pkg_name = ".".join(parts[:i])
            if pkg_name not in sys.modules:
                pkg = types.ModuleType(pkg_name)
                pkg.__path__ = []  # mark as package
                sys.modules[pkg_name] = pkg
    
    # Create a module for this skill's action using the sanitized module_name
    # module_name is namespaced: "{workspace_code}.{base_module}"
    full_module_name = f"dynamic_skills.{module_name}"
    _ensure_virtual_packages(full_module_name)
    module = types.ModuleType(full_module_name)
    module.__file__ = f"<dynamic:{module_name}>"
    
    # Execute the code in the module's namespace
    try:
        exec(code, module.__dict__)
        
        # Get the function from the module
        if not hasattr(module, function_name):
            raise RuntimeError(f"Function '{function_name}' not found in action code")
        
        func = getattr(module, function_name)
        
        # Register in ACTION_REGISTRY
        registry_key = f"{full_module_name}.{function_name}"
        ACTION_REGISTRY[registry_key] = func
        
        # Also add module to sys.modules for imports
        sys.modules[full_module_name] = module
        
        print(f"[SKILL_DB] Registered inline action: {registry_key}")
        
    except Exception as e:
        raise RuntimeError(f"Failed to register inline action for {module_name}: {e}")


def _register_pipeline_functions(module_name: str, functions_code: str):
    """
    Register Python functions for data_pipeline transform steps.
    
    Registers all functions defined in the code into the _ACTION_FUNCTION_REGISTRY.
    
    Args:
        module_name: The Python module name (from module_name column, already sanitized)
        functions_code: The Python code containing the functions
    
    Raises:
        SyntaxError: If the Python code has syntax errors
        RuntimeError: If the code cannot be executed
    """
    import sys
    import types
    from engine import _ACTION_FUNCTION_REGISTRY

    def _ensure_virtual_packages(full_name: str) -> None:
        parts = full_name.split(".")
        for i in range(1, len(parts)):
            pkg_name = ".".join(parts[:i])
            if pkg_name not in sys.modules:
                pkg = types.ModuleType(pkg_name)
                pkg.__path__ = []  # mark as package
                sys.modules[pkg_name] = pkg
    
    # Create a module for this skill's pipeline functions using the sanitized module_name
    # module_name is namespaced: "{workspace_code}.{base_module}"
    full_module_name = f"pipeline_functions.{module_name}"
    _ensure_virtual_packages(full_module_name)
    module = types.ModuleType(full_module_name)
    module.__file__ = f"<pipeline:{module_name}>"
    
    # Execute the code in the module's namespace
    try:
        # First, validate syntax by compiling (this gives better error messages)
        compile(functions_code, f"<pipeline:{module_name}>", 'exec')
        
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
        sys.modules[full_module_name] = module
        
        print(f"[SKILL_DB] Registered {registered_count} pipeline functions for {module_name}")
        
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
        raise RuntimeError(f"Failed to register pipeline functions for {module_name}: {e}")


def save_skill_to_database(skill_data: Dict[str, Any]) -> str:
    """
    Save or update a skill in the database.
    
    - If 'id' is provided: UPDATE that specific skill by ID (name CANNOT be changed)
    - If 'id' is not provided: INSERT new skill (will fail if name+workspace_id already exists)
    
    Module naming is handled in Python code (not triggers):
    - module_name = "{workspace_code}.{sanitized_name}"
    - This ensures consistent, predictable naming without trigger conflicts
    
    Args:
        skill_data: Skill configuration dictionary
        
    Returns:
        Skill ID (UUID as string)
    """
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            workspace_id = skill_data.get("workspace_id")
            if not workspace_id:
                raise ValueError("workspace_id is required to save a database skill (module namespace needs workspace code)")

            # Fetch workspace code
            cur.execute("SELECT code FROM workspaces WHERE id = %s", (workspace_id,))
            ws_row = cur.fetchone()
            if not ws_row or not ws_row[0]:
                raise ValueError(f"Workspace not found or missing code: {workspace_id}")
            workspace_code = ws_row[0]
            
            skill_id = skill_data.get("id")
            
            # Compute module_name only for INSERT (new skills)
            # For UPDATE, we fetch the existing module_name from database (name is immutable)
            if skill_id:
                # UPDATE mode: fetch existing module_name (name cannot change)
                cur.execute("SELECT module_name FROM dynamic_skills WHERE id = %s", (skill_id,))
                existing_row = cur.fetchone()
                if not existing_row:
                    raise ValueError(f"Skill with id {skill_id} not found")
                module_name = existing_row[0]
                print(f"[SKILL_DB] UPDATE mode: reusing existing module_name={module_name}")
            else:
                # INSERT mode: compute new namespaced module_name
                cur.execute("SELECT generate_module_name(%s)", (skill_data["name"],))
                base_module_name = cur.fetchone()[0]
                module_name = f"{workspace_code}.{base_module_name}"
                print(f"[SKILL_DB] INSERT mode: workspace_code={workspace_code}, base={base_module_name}, module_name={module_name}")
            
            # If this is a python_function action, ensure module field is set correctly
            action_config = skill_data.get("action_config")
            if action_config and isinstance(action_config, dict):
                if action_config.get("type") == "python_function":
                    # Always set the module path using the sanitized module_name
                    action_config["module"] = f"dynamic_skills.{module_name}"
            
            if skill_id:
                # UPDATE mode: User provided an ID, update that specific skill
                # NOTE: name is NOT updated (immutable), module_name stays the same
                cur.execute("""
                    UPDATE dynamic_skills SET
                        description = %(description)s,
                        requires = %(requires)s,
                        produces = %(produces)s,
                        optional_produces = %(optional_produces)s,
                        executor = %(executor)s,
                        hitl_enabled = %(hitl_enabled)s,
                        prompt = %(prompt)s,
                        system_prompt = %(system_prompt)s,
                        llm_model = %(llm_model)s,
                        rest_config = %(rest_config)s,
                        action_config = %(action_config)s,
                        action_code = %(action_code)s,
                        action_functions = %(action_functions)s,
                        enabled = %(enabled)s,
                        workspace_id = %(workspace_id)s,
                        owner_id = %(owner_id)s,
                        is_public = %(is_public)s
                    WHERE id = %(id)s
                    RETURNING id::text
                """, {
                    "id": skill_id,
                    "description": skill_data.get("description", ""),
                    "requires": json.dumps(list(skill_data.get("requires", []))),
                    "produces": json.dumps(list(skill_data.get("produces", []))),
                    "optional_produces": json.dumps(list(skill_data.get("optional_produces", []))),
                    "executor": skill_data.get("executor", "llm"),
                    "hitl_enabled": skill_data.get("hitl_enabled", False),
                    "prompt": skill_data.get("prompt"),
                    "system_prompt": skill_data.get("system_prompt"),
                    "llm_model": skill_data.get("llm_model"),
                    "rest_config": json.dumps(skill_data.get("rest_config")) if skill_data.get("rest_config") else None,
                    "action_config": json.dumps(action_config) if action_config else None,
                    "action_code": skill_data.get("action_code"),
                    "action_functions": skill_data.get("action_functions"),
                    "enabled": skill_data.get("enabled", True),
                    "workspace_id": skill_data.get("workspace_id"),
                    "owner_id": skill_data.get("owner_id"),
                    "is_public": skill_data.get("is_public", False),
                })
                
                result = cur.fetchone()
                if not result:
                    raise ValueError(f"Skill with id {skill_id} not found")
                skill_id = result[0]
            else:
                # INSERT mode: No ID provided, create new skill
                # Will fail if (workspace_id, name) already exists due to unique constraint
                cur.execute("""
                    INSERT INTO dynamic_skills (
                        name, module_name, description, requires, produces, optional_produces,
                        executor, hitl_enabled, prompt, system_prompt,
                        llm_model, rest_config, action_config, action_code, action_functions,
                        source, enabled, workspace_id, owner_id, is_public
                    ) VALUES (
                        %(name)s, %(module_name)s, %(description)s, %(requires)s, %(produces)s, %(optional_produces)s,
                        %(executor)s, %(hitl_enabled)s, %(prompt)s, %(system_prompt)s,
                        %(llm_model)s, %(rest_config)s, %(action_config)s, %(action_code)s, %(action_functions)s,
                        'database', %(enabled)s, %(workspace_id)s, %(owner_id)s, %(is_public)s
                    )
                    RETURNING id::text
                """, {
                    "name": skill_data["name"],
                    "module_name": module_name,
                    "description": skill_data.get("description", ""),
                    "requires": json.dumps(list(skill_data.get("requires", []))),
                    "produces": json.dumps(list(skill_data.get("produces", []))),
                    "optional_produces": json.dumps(list(skill_data.get("optional_produces", []))),
                    "executor": skill_data.get("executor", "llm"),
                    "hitl_enabled": skill_data.get("hitl_enabled", False),
                    "prompt": skill_data.get("prompt"),
                    "system_prompt": skill_data.get("system_prompt"),
                    "llm_model": skill_data.get("llm_model"),
                    "rest_config": json.dumps(skill_data.get("rest_config")) if skill_data.get("rest_config") else None,
                    "action_config": json.dumps(action_config) if action_config else None,
                    "action_code": skill_data.get("action_code"),
                    "action_functions": skill_data.get("action_functions"),
                    "enabled": skill_data.get("enabled", True),
                    "workspace_id": skill_data.get("workspace_id"),
                    "owner_id": skill_data.get("owner_id"),
                    "is_public": skill_data.get("is_public", False),
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
                    SELECT id::text, name, description, executor, enabled, created_at, updated_at, source, action_config, llm_model,
                           workspace_id::text, owner_id::text, is_public
                    FROM dynamic_skills
                    ORDER BY name
                """)
                for row in cur.fetchall():
                    skills.append({
                        "id": row[0],
                        "name": row[1],
                        "description": row[2],
                        "executor": row[3],
                        "enabled": row[4],
                        "created_at": row[5].isoformat() if row[5] else None,
                        "updated_at": row[6].isoformat() if row[6] else None,
                        "source": row[7],
                        "action_config": row[8],  # Add action_config
                        "llm_model": row[9],
                        "workspace_id": row[10],
                        "owner_id": row[11],
                        "is_public": bool(row[12]),
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


def reload_skill_registry(workspace_id: Optional[str] = None, include_public: bool = True):
    """
    Reload the skill registry from both filesystem and database.
    
    This allows hot-reload without restarting the application.
    """
    from engine import load_skill_registry, Skill
    import engine
    
    # Load from filesystem
    filesystem_skills = load_skill_registry()
    
    # Load from database
    db_skill_dicts = load_skills_from_database(workspace_id=workspace_id, include_public=include_public)
    db_skills = []
    for skill_dict in db_skill_dicts:
        try:
            skill = Skill(**skill_dict)
            db_skills.append(skill)
        except ValidationError as e:
            print(f"[SKILL_DB] Warning: Invalid skill '{skill_dict.get('name')}': {e}")
    
    # Registry key = module_name only (unique identifier). DB: {code}.{name}; fs: fs.{name}.
    def _skill_key(s):
        return getattr(s, "module_name", None) or f"fs.{s.name}"
    skill_map = {_skill_key(s): s for s in filesystem_skills}
    for db_skill in db_skills:
        skill_map[_skill_key(db_skill)] = db_skill
    engine.SKILL_REGISTRY = list(skill_map.values())
    
    scope_msg = f" for workspace {workspace_id}" if workspace_id else ""
    print(f"[SKILL_DB] Reloaded {len(engine.SKILL_REGISTRY)} skills ({len(filesystem_skills)} from files, {len(db_skills)} from database){scope_msg}")
    
    return len(engine.SKILL_REGISTRY)
