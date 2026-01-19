import os
import json
import asyncio
import importlib
import subprocess
from pathlib import Path
from typing import Annotated, TypedDict, Union, List, Dict, Any, Set, Optional, Type, Callable
from pydantic import BaseModel, Field, ValidationError, create_model, ConfigDict
from enum import Enum
import httpx

import yaml
import psycopg
from langchain_openai import ChatOpenAI
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage, AIMessage, ToolMessage
from langchain_core.tools import tool
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from langgraph.checkpoint.postgres import PostgresSaver
from psycopg_pool import ConnectionPool
from env_loader import load_env_once

from log_stream import publish_log, emit_log, set_db_pool

# Import pub/sub client
from services.pubsub import get_default_client as get_pubsub_client

# Import centralized connection pool
from services.connection_pool import get_postgres_pool, initialize_pools as init_connection_pools

# Import ACTION_REGISTRY for inline Python functions
from actions import ACTION_REGISTRY

class RestConfig(BaseModel):
    url: str
    method: str = "POST"
    headers: Dict[str, str] = Field(default_factory=dict)
    timeout: float = 15.0


class RestToolInput(BaseModel):
    """
    Input schema for the standard agent-level REST tool (not the skill-to-skill REST executor).
    """

    url: str = Field(description="Absolute URL to call")
    method: str = Field(
        default="GET", description="HTTP method such as GET, POST, PUT, PATCH, DELETE"
    )
    params: Dict[str, Any] = Field(default_factory=dict, description="Query params")
    headers: Dict[str, str] = Field(default_factory=dict)
    json_body: Optional[Dict[str, Any]] = Field(
        default=None, alias="json", description="JSON body to send when applicable"
    )
    data: Optional[Any] = Field(
        default=None, description="Raw body when JSON is not suitable (e.g., form-encoded)"
    )
    timeout: float = Field(
        default=10.0, ge=0.5, le=60.0, description="Per-request timeout in seconds"
    )

    model_config = ConfigDict(populate_by_name=True)


class ActionType(str, Enum):
    """Types of action executors available"""
    PYTHON_FUNCTION = "python_function"
    DATA_QUERY = "data_query"
    DATA_PIPELINE = "data_pipeline"
    SCRIPT = "script"
    HTTP_CALL = "http_call"


class ActionConfig(BaseModel):
    """
    Configuration for action-based skill execution.
    Actions are deterministic operations executed by the framework (not LLM).
    
    Skill-local actions:
    - Omit 'module' to auto-discover action.py in skill folder
    - Use relative script_path for skill-local scripts
    - Module starting with '.' is relative to skill folder
    """
    type: ActionType
    
    # For python_function type
    function: Optional[str] = Field(default=None, description="Function name to call")
    module: Optional[str] = Field(
        default=None, 
        description="Module path or omit for skill-local action.py auto-discovery"
    )
    
    # For data_query type
    source: Optional[str] = Field(default=None, description="Data source: postgres, mongodb, redis")
    query: Optional[str] = Field(default=None, description="Query string or template")
    collection: Optional[str] = Field(default=None, description="Collection/table name")
    filter: Optional[Dict[str, Any]] = Field(default=None, description="Query filter for NoSQL")
    
    # Database configuration (skill-local)
    credential_ref: Optional[str] = Field(
        default=None,
        description="Reference to credential in secure vault (e.g., 'my_postgres_db')"
    )
    db_config_file: Optional[str] = Field(
        default=None,
        description="[DEPRECATED] Path to db_config.json (use credential_ref instead)"
    )
    
    # For data_pipeline type
    steps: Optional[List[Dict[str, Any]]] = Field(
        default=None,
        description="List of pipeline steps with source, query, transform, etc."
    )
    
    # For script type
    script_path: Optional[str] = Field(
        default=None, 
        description="Path to script file (relative paths resolve from skill folder)"
    )
    interpreter: Optional[str] = Field(default="python", description="Script interpreter")
    
    # For http_call type
    url: Optional[str] = Field(default=None, description="HTTP endpoint URL")
    method: Optional[str] = Field(default="GET", description="HTTP method")
    headers: Optional[Dict[str, str]] = Field(default_factory=dict, description="HTTP headers")
    
    # Common settings
    timeout: float = Field(default=30.0, description="Execution timeout in seconds")
    retry: int = Field(default=0, ge=0, le=5, description="Number of retries on failure")


# --- 1. MODELS & REGISTRY ---
class Skill(BaseModel):
    name: str
    description: str
    requires: Set[str]
    produces: Set[str]
    optional_produces: Set[str] = set()
    hitl_enabled: bool = False
    prompt: Optional[str] = None          # task/user intent prompt
    system_prompt: Optional[str] = None   # business SOPs / policies
    executor: str = "llm"  # "llm" (default), "rest", or "action"
    rest: Optional[RestConfig] = None
    action: Optional[ActionConfig] = None  # Configuration for action executor
    workspace_id: Optional[str] = None  # Workspace isolation (None = public/filesystem)
    owner_id: Optional[str] = None  # Skill owner
    is_public: bool = False  # Visibility outside workspace
    workspace_id: Optional[str] = None     # Workspace that owns the skill
    owner_id: Optional[str] = None         # User who owns the skill
    is_public: bool = True                 # Public skills are visible across workspaces

class PlannerDecision(BaseModel):
    next_agent: str = Field(description="Name of agent or 'END'")
    reasoning: str = Field(description="Reasoning for the decision")

# --- Skill Loader (Markdown-based, Anthropic-style registry) ---
def _parse_skill_md(md_text: str) -> tuple[Dict[str, Any], str]:
    lines = md_text.splitlines()
    if not lines or lines[0].strip() != "---":
        raise ValueError("Skill file must start with frontmatter delimited by '---'.")

    end_idx = None
    for idx in range(1, len(lines)):
        if lines[idx].strip() == "---":
            end_idx = idx
            break
    if end_idx is None:
        raise ValueError("Skill file frontmatter must be closed with '---'.")

    frontmatter = "\n".join(lines[1:end_idx])
    meta = yaml.safe_load(frontmatter) or {}
    body = "\n".join(lines[end_idx + 1:]).strip()
    return meta, body


def _coerce_set(value: Any, field_name: str) -> Set[str]:
    if value is None:
        return set()
    if isinstance(value, (list, set, tuple)):
        return set(str(v) for v in value)
    raise ValueError(f"Field '{field_name}' must be a list or set of strings.")


def _resolve_skill_local_action(action_cfg: ActionConfig, skill_dir: Path, skill_name: str) -> ActionConfig:
    """
    Resolve skill-local action paths and auto-discover local action files.
    
    Convention:
    - If module not specified and action.py exists → use it
    - If script_path is relative → resolve from skill directory
    - If function/module starts with '.' → treat as skill-local
    """
    
    # Store skill path for later use (e.g., resolving db_config.json)
    action_cfg._skill_path = skill_dir
    
    # Handle python_function with skill-local module
    if action_cfg.type == ActionType.PYTHON_FUNCTION:
        # If no module specified, look for action.py in skill folder
        if not action_cfg.module:
            action_file = skill_dir / "action.py"
            if action_file.exists():
                # Create dynamic module name based on skill
                action_cfg.module = f"skills.{skill_name}.action"
                emit_log(f"[SKILL-LOCAL] Auto-discovered action.py for {skill_name}")
        
        # If module starts with '.', it's relative to skill folder
        elif action_cfg.module.startswith('.'):
            action_cfg.module = f"skills.{skill_name}{action_cfg.module}"
    
    # Handle script with skill-local path
    elif action_cfg.type == ActionType.SCRIPT:
        if action_cfg.script_path and not Path(action_cfg.script_path).is_absolute():
            # Resolve relative to skill directory
            script_path = skill_dir / action_cfg.script_path
            if not script_path.exists():
                # Try common names: script.py, run.py, execute.sh, etc.
                for candidate in ["script.py", "run.py", "execute.py", "script.sh", "run.sh"]:
                    candidate_path = skill_dir / candidate
                    if candidate_path.exists():
                        script_path = candidate_path
                        emit_log(f"[SKILL-LOCAL] Auto-discovered {candidate} for {skill_name}")
                        break
            
            action_cfg.script_path = str(script_path.absolute())
    
    return action_cfg


def _register_skill_local_actions(action_cfg: ActionConfig, skill_dir: Path, skill_name: str):
    """
    Register skill-local action functions at skill load time.
    This allows skills to be self-contained with their own action code.
    """
    if action_cfg.type != ActionType.PYTHON_FUNCTION:
        return
    
    if not action_cfg.module or not action_cfg.function:
        return
    
    # Check if this is a skill-local module
    if f"skills.{skill_name}" not in action_cfg.module:
        return
    
    # Load the skill-local module dynamically
    action_file = skill_dir / "action.py"
    if not action_file.exists():
        return
    
    try:
        # Add skill directory to sys.path temporarily
        import sys
        skill_parent = skill_dir.parent.parent  # Go up to project root
        if str(skill_parent) not in sys.path:
            sys.path.insert(0, str(skill_parent))
        
        # Import the module
        module = importlib.import_module(action_cfg.module)
        
        # Get the function
        if hasattr(module, action_cfg.function):
            func = getattr(module, action_cfg.function)
            func_key = f"{action_cfg.module}.{action_cfg.function}"
            
            # Register it
            if func_key not in _ACTION_FUNCTION_REGISTRY:
                register_action_function(func_key, func)
                emit_log(f"[SKILL-LOCAL] Registered {func_key} from {skill_name}")
        else:
            emit_log(f"[SKILL-LOCAL] Warning: Function '{action_cfg.function}' not found in {action_cfg.module}")
            
    except Exception as e:
        emit_log(f"[SKILL-LOCAL] Failed to load action for {skill_name}: {e}")


def load_skill_registry(skills_dir: Optional[Path] = None) -> List[Skill]:
    base_dir = skills_dir or (Path(__file__).parent / "skills")
    if not base_dir.exists():
        raise RuntimeError(f"Skills directory not found: {base_dir}")

    registry: List[Skill] = []
    seen_names: Set[str] = set()

    def register_skill(md_file: Path):
        raw = md_file.read_text(encoding="utf-8")
        meta, body_text = _parse_skill_md(raw)

        prompt_text = meta.get("prompt")
        prompt_file = md_file.parent / "prompt.md"
        if prompt_file.exists():
            prompt_candidate = prompt_file.read_text(encoding="utf-8").strip()
            if prompt_candidate:
                prompt_text = prompt_candidate

        system_prompt = (meta.get("system_prompt") or "").strip()
        if not system_prompt and body_text:
            # Use the body of skill.md as the default system prompt/SOPs.
            system_prompt = body_text

        try:
            name = meta["name"]
            description = meta.get("description", "")
            requires = _coerce_set(meta.get("requires"), "requires")
            produces = _coerce_set(meta.get("produces"), "produces")
            optional_produces = _coerce_set(meta.get("optional_produces"), "optional_produces")
            hitl_enabled = bool(meta.get("hitl_enabled", False))
            executor = str(meta.get("executor", "llm")).lower()

            rest_cfg = None
            if executor == "rest":
                rest_meta = meta.get("rest") or {}
                try:
                    rest_cfg = RestConfig(**rest_meta)
                except ValidationError as exc:
                    raise RuntimeError(f"Invalid REST config for skill '{name}' in {md_file}: {exc}") from exc
            
            action_cfg = None
            if executor == "action":
                action_meta = meta.get("action") or {}
                try:
                    action_cfg = ActionConfig(**action_meta)
                    # Auto-discover skill-local actions
                    action_cfg = _resolve_skill_local_action(action_cfg, md_file.parent, name)
                except ValidationError as exc:
                    raise RuntimeError(f"Invalid action config for skill '{name}' in {md_file}: {exc}") from exc
        except KeyError as exc:
            raise RuntimeError(f"Missing required field {exc} in {md_file}") from exc

        if name in seen_names:
            raise RuntimeError(f"Duplicate skill name detected: {name}")
        
        # Auto-register skill-local action functions at load time
        if executor == "action" and action_cfg:
            _register_skill_local_actions(action_cfg, md_file.parent, name)

        registry.append(
            Skill(
                name=name,
                description=description,
                requires=requires,
                produces=produces,
                optional_produces=optional_produces,
                hitl_enabled=hitl_enabled,
                prompt=prompt_text,
                system_prompt=system_prompt or None,
                executor=executor,
                rest=rest_cfg,
                action=action_cfg,
            )
        )
        seen_names.add(name)

    # Preferred: folder-per-skill with skill.md
    for entry in base_dir.iterdir():
        if entry.is_dir():
            skill_md = entry / "skill.md"
            if skill_md.exists():
                register_skill(skill_md)

    # Back-compat: allow top-level *.md except skills.md
    for md_file in base_dir.glob("*.md"):
        if md_file.name.lower() == "skills.md":
            continue
        register_skill(md_file)

    if not registry:
        raise RuntimeError(f"No skills found in {base_dir}")

    return registry

# --- 2. STATE DEFINITION ---
class AgentState(TypedDict):
    layman_sop: str
    data_store: Dict[str, Any]
    active_skill: Optional[str]
    history: Annotated[List[str], lambda x, y: x + y]
    thread_id: str
    workspace_id: Optional[str]
    execution_sequence: Optional[List[str]]  # Track skill execution order for loop detection


# --- Utilities ---
def _require_openai_api_key() -> str:
    key = os.getenv("OPENAI_API_KEY")
    if not key:
        raise RuntimeError(
            "Missing OPENAI_API_KEY. Set it in your environment or .env before running."
        )
    return key


def _get_env_value(key: str, default: str = "") -> str:
    """Fetch an env var and fall back when unset or blank."""
    value = os.getenv(key)
    if value is None:
        return default
    value = value.strip()
    return value if value else default


def _structured_llm(schema: Type[BaseModel], *, temperature: float = 0):
    api_key = _require_openai_api_key()
    return ChatOpenAI(model="gpt-4o", temperature=temperature, api_key=api_key).with_structured_output(
        schema, method="function_calling"
    )


def _iter_available_paths(obj: Any, prefix: str = "") -> Set[str]:
    """
    Recursively collect dot-notation paths for all present (non-empty) values.
    Skips internal keys starting with underscore.
    """
    paths: Set[str] = set()

    def _is_present(val: Any) -> bool:
        if val is None:
            return False
        if isinstance(val, str) and not val.strip():
            return False
        return True

    if isinstance(obj, dict):
        for key, val in obj.items():
            if str(key).startswith("_"):
                continue
            new_prefix = key if not prefix else f"{prefix}.{key}"
            if _is_present(val):
                paths.add(new_prefix)
            paths.update(_iter_available_paths(val, new_prefix))
    elif isinstance(obj, list):
        for idx, val in enumerate(obj):
            new_prefix = f"{prefix}.{idx}" if prefix else str(idx)
            if _is_present(val):
                paths.add(new_prefix)
            paths.update(_iter_available_paths(val, new_prefix))
    return paths


def _available_keys(store: Dict[str, Any]) -> Set[str]:
    """
    Treat missing/empty values as unavailable. Booleans and zeros are valid.
    Strings that are None or empty/whitespace are treated as missing.
    Returns dot-notation paths for nested objects so planners can gate on them.
    """
    return _iter_available_paths(store)


def _last_executed(history: List[str]) -> Optional[str]:
    """Return the most recent executed skill from history, if any."""
    for entry in reversed(history):
        if entry.startswith("Executed "):
            return entry.replace("Executed ", "", 1)
    return None


def _completed_skills(history: List[str]) -> Set[str]:
    """Collect skill names that have been executed (including REST callbacks)."""
    completed: Set[str] = set()
    for entry in history:
        if entry.startswith("Executed "):
            completed.add(entry.replace("Executed ", "", 1).replace(" (REST callback)", ""))
    return completed


def _detect_infinite_loop(execution_sequence: List[str]) -> Optional[str]:
    """
    Detect infinite loops in skill execution.
    
    Rules:
    - If the same skill executes 3+ times in a row: LOOP
    - If pattern A->B->A->B or A->B->C->A->B->C detected: LOOP
    
    Returns error message if loop detected, None otherwise.
    """
    if not execution_sequence or len(execution_sequence) < 3:
        return None
    
    # Get last 6 executions for pattern detection
    recent = execution_sequence[-6:]
    
    # Rule 1: Same skill executed 3+ times consecutively
    if len(recent) >= 3:
        last_three = recent[-3:]
        if last_three[0] == last_three[1] == last_three[2]:
            return f"Infinite loop detected: '{last_three[0]}' executed 3 times in a row"
    
    # Rule 2: Alternating pattern A->B->A->B (2 skills repeating)
    if len(recent) >= 4:
        last_four = recent[-4:]
        if last_four[0] == last_four[2] and last_four[1] == last_four[3]:
            return f"Infinite loop detected: alternating pattern '{last_four[0]}' -> '{last_four[1]}' -> '{last_four[0]}' -> '{last_four[1]}'"
    
    # Rule 3: Three-skill cycle A->B->C->A->B->C
    if len(recent) >= 6:
        if recent[0] == recent[3] and recent[1] == recent[4] and recent[2] == recent[5]:
            return f"Infinite loop detected: cycle pattern '{recent[0]}' -> '{recent[1]}' -> '{recent[2]}' repeating"
    
    return None


def _get_path_value(data: Dict[str, Any], path: str) -> Any:
    """Return value at dot-notation path; supports numeric list indices."""
    parts = path.split(".")
    cur: Any = data
    for part in parts:
        if isinstance(cur, dict):
            cur = cur.get(part)
        elif isinstance(cur, list) and part.isdigit():
            idx = int(part)
            if idx >= len(cur):
                return None
            cur = cur[idx]
        else:
            return None
    return cur


def _set_path_value(data: Dict[str, Any], path: str, value: Any) -> Dict[str, Any]:
    """
    Return a new dict with the value set at the given dot-notation path.
    Creates intermediate dicts as needed; overwrites non-dict intermediates.
    """
    parts = path.split(".")

    def _set(obj: Any, idx: int) -> Any:
        if idx == len(parts):
            return value
        key = parts[idx]
        base = dict(obj) if isinstance(obj, dict) else {}
        next_obj = base.get(key, {})
        base[key] = _set(next_obj if isinstance(next_obj, dict) else {}, idx + 1)
        return base

    return _set(data if isinstance(data, dict) else {}, 0)


def _deep_merge_dict(base: Dict[str, Any], incoming: Dict[str, Any]) -> Dict[str, Any]:
    """
    Recursively merge incoming into base without mutating inputs.
    Dicts merge deeply; other types (including lists) overwrite.
    """
    result = dict(base) if isinstance(base, dict) else {}
    for key, val in incoming.items():
        if key in result and isinstance(result[key], dict) and isinstance(val, dict):
            result[key] = _deep_merge_dict(result[key], val)
        else:
            result[key] = val
    return result


def _rest_pending(store: Dict[str, Any]) -> Set[str]:
    pending = store.get("_rest_pending", set())
    if isinstance(pending, list):
        return set(pending)
    if isinstance(pending, set):
        return pending
    return set()


def _mark_rest_pending(store: Dict[str, Any], skill_name: str) -> Dict[str, Any]:
    pending = _rest_pending(store)
    pending.add(skill_name)
    return {**store, "_rest_pending": list(pending)}


def _clear_rest_pending(store: Dict[str, Any], skill_name: str) -> Dict[str, Any]:
    pending = _rest_pending(store)
    pending.discard(skill_name)
    if not pending:
        new_store = dict(store)
        new_store.pop("_rest_pending", None)
        return new_store
    return {**store, "_rest_pending": list(pending)}


def _callback_url() -> str:
    base = os.getenv("CALLBACK_BASE_URL", "http://localhost:8000")
    return base.rstrip("/") + "/callback"


def _progress_summary(state: AgentState) -> List[str]:
    """Generate a short summary for planner context."""
    summary: List[str] = []
    order_no = _get_path_value(state.get("data_store", {}), "order_number")
    if order_no:
        summary.append(f"Order number: {order_no}")
    completed = _completed_skills(state.get("history", []))
    for name in sorted(completed):
        summary.append(f"{name}: completed")
    return summary


def _format_with_ctx(template: str, ctx: Dict[str, Any]) -> str:
    """
    Render a string template using values from ctx.
    Raises a clear error if placeholders are missing.
    """
    try:
        return template.format(**ctx)
    except KeyError as exc:
        raise RuntimeError(f"Missing placeholder value for {exc} in template: {template}") from exc


def _safe_serialize(obj: Any, limit: int = 3000) -> str:
    """Best-effort JSON serialization with truncation to keep tokens bounded."""
    try:
        rendered = json.dumps(obj, default=str)
    except Exception:
        rendered = str(obj)
    if len(rendered) > limit:
        return rendered[:limit] + "...(truncated)"
    return rendered


@tool("http_request", args_schema=RestToolInput)
async def _http_request_tool(
    url: str,
    method: str = "GET",
    params: Optional[Dict[str, Any]] = None,
    headers: Optional[Dict[str, str]] = None,
    json_body: Optional[Dict[str, Any]] = None,
    data: Optional[Any] = None,
    timeout: float = 10.0,
):
    """
    Standard REST call tool for the LLM (agent-level). Use this for ad-hoc API
    calls inside a skill. This is distinct from the skill-level REST executor
    that dispatches to other agents via callbacks.
    """
    method = (method or "GET").upper()
    params = params or None
    headers = headers or None

    try:
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            response = await client.request(
                method,
                url,
                params=params,
                headers=headers,
                json=json_body,
                data=data,
            )
        content_type = response.headers.get("content-type", "")
        if "application/json" in content_type.lower():
            body: Any = response.json()
        else:
            text = response.text or ""
            body = text if len(text) <= 2000 else text[:2000] + "...(truncated)"
        return {
            "status": response.status_code,
            "headers": {
                k: v
                for k, v in response.headers.items()
                if k.lower() in {"content-type", "location"}
            },
            "body": body,
        }
    except Exception as exc:
        return {"error": str(exc)}


def _agent_tools() -> List[Any]:
    """Tools available to the LLM inside a skill execution."""
    return [_http_request_tool]


async def _run_agent_tools(
    messages: List[BaseMessage], *, max_rounds: int = 2
) -> tuple[List[Dict[str, Any]], List[BaseMessage]]:
    """
    Allow the LLM to invoke agent-level tools (e.g., REST calls) before
    producing the structured skill output. Returns tool run info and the
    expanded message history including tool results.
    """
    tools = _agent_tools()
    if not tools:
        return [], messages

    api_key = _require_openai_api_key()
    tool_llm = ChatOpenAI(model="gpt-4o-mini", temperature=0, api_key=api_key).bind_tools(tools)
    history: List[BaseMessage] = list(messages)
    tool_runs: List[Dict[str, Any]] = []

    for round_idx in range(max_rounds):
        ai_msg: AIMessage = await tool_llm.ainvoke(history)
        history.append(ai_msg)
        tool_calls = getattr(ai_msg, "tool_calls", None) or []
        if not tool_calls:
            return tool_runs, history

        for call in tool_calls:
            name = getattr(call, "name", None) or (call.get("name") if isinstance(call, dict) else None)
            args = getattr(call, "args", None) or (call.get("args") if isinstance(call, dict) else {}) or {}
            call_id = getattr(call, "id", None) or (call.get("id") if isinstance(call, dict) else "tool_call")

            selected_tool = next((t for t in tools if t.name == name), None)
            if not selected_tool:
                result: Dict[str, Any] = {"error": f"Unknown tool '{name}'"}
            else:
                result = await selected_tool.ainvoke(args)
            tool_runs.append({"tool": name, "args": args, "result": result})
            history.append(ToolMessage(content=_safe_serialize(result), tool_call_id=call_id))

        await publish_log(f"[EXECUTOR] Tool round {round_idx + 1} completed with tools {[r['tool'] for r in tool_runs]}")

    await publish_log(f"[EXECUTOR] Reached max tool rounds ({max_rounds}); proceeding with available context.")
    return tool_runs, history


# --- ACTION REGISTRY & DISCOVERY ---
_ACTION_FUNCTION_REGISTRY: Dict[str, Callable] = {}


def register_action_function(name: str, func: Callable):
    """Register a plain Python function as an action"""
    _ACTION_FUNCTION_REGISTRY[name] = func
    emit_log(f"[ACTIONS] Registered function: {name}")


def auto_discover_actions(modules: List[str]):
    """
    Auto-discover functions decorated with @action from specified modules.
    Call this at startup to register all available actions.
    """
    for module_path in modules:
        try:
            module = importlib.import_module(module_path)
            for attr_name in dir(module):
                attr = getattr(module, attr_name)
                if callable(attr) and hasattr(attr, '_is_action'):
                    func_name = getattr(attr, '_action_name', attr_name)
                    full_name = f"{module_path}.{func_name}"
                    register_action_function(full_name, attr)
                    emit_log(f"[ACTIONS] Auto-discovered: {full_name}")
        except ImportError as e:
            emit_log(f"[ACTIONS] Could not import module '{module_path}': {e}")
        except Exception as e:
            emit_log(f"[ACTIONS] Error discovering actions in '{module_path}': {e}")


async def _execute_rest_skill(skill_meta: Skill, state: AgentState, input_ctx: Dict[str, Any]):
    if not skill_meta.rest:
        raise RuntimeError(f"{skill_meta.name} is missing REST configuration.")

    # Safety check: don't dispatch if already pending (prevents duplicate REST calls)
    pending_rest = _rest_pending(state["data_store"])
    if skill_meta.name in pending_rest:
        await publish_log(f"[EXECUTOR] {skill_meta.name} already pending REST callback. Skipping duplicate dispatch.")
        # Return current state unchanged - workflow will pause at await_callback
        return {
            "history": [f"Skipped duplicate REST dispatch for {skill_meta.name}"],
            "active_skill": skill_meta.name,
            "data_store": state["data_store"],
        }

    payload = {
        "skill": skill_meta.name,
        "thread_id": state["thread_id"],
        "callback_url": _callback_url(),
        "inputs": input_ctx,
        "expected_outputs": sorted(skill_meta.produces | skill_meta.optional_produces),
        "sop": state["layman_sop"],
    }

    rest_url = _format_with_ctx(skill_meta.rest.url, input_ctx)

    async with httpx.AsyncClient(timeout=skill_meta.rest.timeout) as client:
        response = await client.request(
            skill_meta.rest.method,
            rest_url,
            json=payload,
            headers=skill_meta.rest.headers,
        )
        response.raise_for_status()

    await publish_log(f"[EXECUTOR] {skill_meta.name} dispatched to REST endpoint {rest_url}")
    updated_store = _mark_rest_pending(state["data_store"], skill_meta.name)
    return {
        "history": [f"Requested {skill_meta.name} via REST API"],
        "active_skill": skill_meta.name,
        "data_store": updated_store,
    }


# --- ACTION EXECUTORS ---

async def _execute_python_function(cfg: ActionConfig, inputs: Dict[str, Any], state: AgentState) -> Dict[str, Any]:
    """Execute a plain Python function"""
    if not cfg.function or not cfg.module:
        raise ValueError("python_function action requires 'function' and 'module' fields")
    
    func_key = f"{cfg.module}.{cfg.function}"
    
    # Try ACTION_REGISTRY first (for inline database skills)
    if func_key in ACTION_REGISTRY:
        func = ACTION_REGISTRY[func_key]
    # Then try _ACTION_FUNCTION_REGISTRY (for pipeline transforms)
    elif func_key in _ACTION_FUNCTION_REGISTRY:
        func = _ACTION_FUNCTION_REGISTRY[func_key]
    else:
        # Dynamic import if not registered (for filesystem skills)
        try:
            module = importlib.import_module(cfg.module)
            func = getattr(module, cfg.function)
            ACTION_REGISTRY[func_key] = func
            emit_log(f"[ACTIONS] Dynamically loaded: {func_key}")
        except ImportError as e:
            raise RuntimeError(f"Cannot import module '{cfg.module}': {e}") from e
        except AttributeError as e:
            raise RuntimeError(f"Function '{cfg.function}' not found in module '{cfg.module}': {e}") from e
    
    # Execute function (handle both sync and async)
    try:
        if asyncio.iscoroutinefunction(func):
            result = await func(**inputs)
        else:
            # Run sync function in thread pool to avoid blocking
            # Pass inputs as keyword arguments to thread
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(None, lambda: func(**inputs))
    except TypeError as e:
        # Better error message for argument mismatches
        import inspect
        sig = inspect.signature(func)
        expected = set(sig.parameters.keys())
        provided = set(inputs.keys())
        
        if expected != provided:
            missing = expected - provided
            extra = provided - expected
            msg = f"Function '{cfg.function}' signature mismatch."
            if missing:
                msg += f" Missing parameters: {missing}."
            if extra:
                msg += f" Extra parameters: {extra}."
            msg += f" Expected: {sorted(expected)}, Provided: {sorted(provided)}"
            raise RuntimeError(msg) from e
        else:
            # Same parameters but still TypeError - re-raise original
            raise
    
    # Ensure result is a dict
    if not isinstance(result, dict):
        raise ValueError(f"Function {func_key} must return a dict, got {type(result)}")
    
    return result


async def _execute_data_query(cfg: ActionConfig, inputs: Dict[str, Any]) -> Dict[str, Any]:
    """Execute a database query"""
    if not cfg.source:
        raise ValueError("data_query action requires 'source' field")
    
    source = cfg.source.lower()
    
    if source == "postgres":
        return await _execute_postgres_query(cfg, inputs)
    elif source == "mongodb":
        return await _execute_mongodb_query(cfg, inputs)
    elif source == "redis":
        return await _execute_redis_query(cfg, inputs)
    else:
        raise ValueError(f"Unknown data source: {cfg.source}")


async def _resolve_database_uri(
    cfg: ActionConfig, 
    inputs: Dict[str, Any],
    db_type: str
) -> str:
    """
    Resolve database URI with support for secure credentials.
    
    Resolution order:
    1. Direct credential_ref in action config (recommended)
    2. Skill-local db_config.json with credential reference (deprecated but supported)
    3. Global DATABASE_URL environment variable (fallback)
    
    Args:
        cfg: Action configuration
        inputs: Input context (may contain user_context)
        db_type: Database type (postgres, mongodb, etc.)
    
    Returns:
        Connection URI string
    """
    # Option 1: Direct credential reference (recommended)
    if cfg.credential_ref:
        return await _resolve_secure_credential(cfg, inputs, cfg.credential_ref)
    
    # Option 2: Skill-local db_config.json (deprecated but supported)
    if cfg.db_config_file:
        return await _resolve_secure_credential_from_file(cfg, inputs)
    
    # Option 3: Global environment variable (fallback)
    db_uri = _get_env_value("DATABASE_URL", "")
    if not db_uri:
        raise RuntimeError(
            f"Database configuration not found. Either:\n"
            f"  1. Set 'credential_ref' in skill action config for secure credentials, or\n"
            f"  2. Set DATABASE_URL environment variable\n"
            f"\n"
            f"Example:\n"
            f"  action:\n"
            f"    type: data_query\n"
            f"    source: postgres\n"
            f"    credential_ref: 'my_postgres_db'"
        )
    
    await publish_log(f"[ACTIONS] Using global DATABASE_URL for {db_type}")
    return db_uri


async def _resolve_secure_credential(
    cfg: ActionConfig,
    inputs: Dict[str, Any],
    credential_ref: str
) -> str:
    """
    Resolve database credentials from secure vault using credential reference.
    
    Args:
        cfg: Action configuration
        inputs: Input context (may contain user_context, or uses global auth)
        credential_ref: Name or ID of credential in vault
    
    Gets user_context from inputs or global AuthContext.
    """
    try:
        from services.credentials import get_vault, UserContext, get_current_user
    except ImportError:
        raise RuntimeError(
            "Secure credentials system not available. "
            "Install required dependencies: pip install cryptography"
        )
    
    # Get user context for authorization
    # Try inputs first, then fall back to global AuthContext
    user_context = inputs.get("user_context")
    if not user_context:
        try:
            user_context = get_current_user()
            await publish_log(
                f"[ACTIONS] Using global auth context for user {user_context.user_id}"
            )
        except RuntimeError:
            raise RuntimeError(
                "user_context required for secure credentials. Either:\n"
                "  1. Pass user_context in inputs, or\n"
                "  2. Initialize global auth at startup:\n"
                "     from services.credentials import AuthContext, get_system_user\n"
                "     AuthContext.initialize(get_system_user())"
            )
    
    # Convert dict to UserContext if needed
    if isinstance(user_context, dict):
        user_context = UserContext(**user_context)
    
    # Resolve credential from vault
    vault = get_vault()
    try:
        credential = vault.get_credential(user_context, credential_ref)
        await publish_log(
            f"[ACTIONS] Using secure credential '{credential_ref}' "
            f"for user {user_context.user_id}"
        )
    except Exception as e:
        raise RuntimeError(
            f"Failed to resolve credential '{credential_ref}': {e}\n"
            f"Make sure the credential exists and belongs to user {user_context.user_id}\n"
            f"\n"
            f"To create a credential:\n"
            f"  python -m scripts.credential_manager add --user {user_context.user_id} --name {credential_ref}"
        )
    
    # Build connection string
    return vault.build_connection_string(credential)


async def _resolve_secure_credential_from_file(
    cfg: ActionConfig,
    inputs: Dict[str, Any]
) -> str:
    """
    [DEPRECATED] Resolve database credentials from skill-local db_config.json.
    
    Use credential_ref directly in action config instead.
    """
    import json
    from pathlib import Path
    
    try:
        from services.credentials import get_vault, UserContext
    except ImportError:
        raise RuntimeError(
            "Secure credentials system not available. "
            "Install required dependencies: pip install cryptography"
        )
    
    # Get user context for authorization
    user_context = inputs.get("user_context")
    if not user_context:
        raise RuntimeError(
            "user_context required in inputs for secure credentials. "
            "Pass UserContext(user_id='...', username='...', roles=[]) in inputs."
        )
    
    # Convert dict to UserContext if needed
    if isinstance(user_context, dict):
        user_context = UserContext(**user_context)
    
    # Get skill path from config
    skill_path = cfg._skill_path if hasattr(cfg, '_skill_path') else None
    if not skill_path:
        raise RuntimeError(
            "Skill path not available. This is a framework bug - "
            "skill path should be set during skill loading."
        )
    
    # Load db_config.json
    config_path = Path(skill_path) / cfg.db_config_file
    if not config_path.exists():
        raise FileNotFoundError(
            f"Database config file not found: {config_path}\n"
            f"Create db_config.json in skill folder with credential reference."
        )
    
    try:
        db_config = json.loads(config_path.read_text())
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON in {config_path}: {e}")
    
    # Get credential reference
    credential_ref = db_config.get("credential_ref")
    if not credential_ref:
        raise ValueError(
            f"db_config.json must contain 'credential_ref' field.\n"
            f"Example: {{'credential_ref': 'my_postgres_db'}}"
        )
    
    await publish_log(
        f"[ACTIONS] WARNING: db_config_file is deprecated. "
        f"Use 'credential_ref: {credential_ref}' directly in action config instead."
    )
    
    # Resolve credential from vault
    vault = get_vault()
    try:
        credential = vault.get_credential(user_context, credential_ref)
        await publish_log(
            f"[ACTIONS] Using secure credential '{credential_ref}' "
            f"for user {user_context.user_id}"
        )
    except Exception as e:
        raise RuntimeError(
            f"Failed to resolve credential '{credential_ref}': {e}\n"
            f"Make sure the credential exists and belongs to user {user_context.user_id}"
        )
    
    # Build connection string with optional overrides
    overrides = {
        "host": db_config.get("host"),
        "port": db_config.get("port"),
        "database": db_config.get("database")
    }
    overrides = {k: v for k, v in overrides.items() if v is not None}
    
    return vault.build_connection_string(credential, overrides if overrides else None)


async def _execute_postgres_query(cfg: ActionConfig, inputs: Dict[str, Any]) -> Dict[str, Any]:
    """
    Execute a PostgreSQL query using the shared connection pool.
    
    Supports both global DATABASE_URL and skill-local secure credentials.
    """
    import psycopg
    
    if not cfg.query:
        raise ValueError("postgres query requires 'query' field")
    
    # Format query with input context
    query = _format_with_ctx(cfg.query, inputs)
    
    # Check if we should use custom credentials or shared pool
    use_custom_credentials = cfg.credential_ref or cfg.db_config_file
    
    if use_custom_credentials:
        # Use skill-specific credentials (creates temporary connection)
        db_uri = await _resolve_database_uri(cfg, inputs, "postgres")
        
        # Execute query in thread to avoid blocking
        def _execute_sync():
            with psycopg.connect(db_uri) as conn:
                with conn.cursor() as cur:
                    cur.execute(query)
                    
                    # Check if query returns results
                    if cur.description:
                        columns = [desc[0] for desc in cur.description]
                        rows = cur.fetchall()
                        return {
                            "query_result": [dict(zip(columns, row)) for row in rows],
                            "row_count": len(rows)
                        }
                    else:
                        # INSERT/UPDATE/DELETE
                        return {
                            "affected_rows": cur.rowcount
                        }
        
        try:
            result = await asyncio.to_thread(_execute_sync)
            await publish_log(f"[ACTIONS] Postgres query executed with custom credentials")
            return result
        except Exception as e:
            raise RuntimeError(f"Postgres query failed: {e}") from e
    else:
        # Use shared connection pool (preferred for performance)
        try:
            pool = get_postgres_pool()
            
            # Execute query in thread to avoid blocking
            def _execute_sync_pooled():
                with pool.connection() as conn:
                    with conn.cursor() as cur:
                        cur.execute(query)
                        
                        # Check if query returns results
                        if cur.description:
                            columns = [desc[0] for desc in cur.description]
                            rows = cur.fetchall()
                            return {
                                "query_result": [dict(zip(columns, row)) for row in rows],
                                "row_count": len(rows)
                            }
                        else:
                            # INSERT/UPDATE/DELETE
                            return {
                                "affected_rows": cur.rowcount
                            }
            
            result = await asyncio.to_thread(_execute_sync_pooled)
            await publish_log(f"[ACTIONS] Postgres query executed with shared pool")
            return result
        except Exception as e:
            raise RuntimeError(f"Postgres query failed: {e}") from e


async def _execute_mongodb_query(cfg: ActionConfig, inputs: Dict[str, Any]) -> Dict[str, Any]:
    """Execute a MongoDB query"""
    from data.mongo import get_collection
    
    if not cfg.collection:
        raise ValueError("mongodb query requires 'collection' field")
    
    collection = get_collection(cfg.collection)
    
    # Format filter with input context
    filter_dict = cfg.filter or {}
    formatted_filter = {}
    for key, value in filter_dict.items():
        if isinstance(value, str):
            formatted_filter[key] = _format_with_ctx(value, inputs)
        else:
            formatted_filter[key] = value
    
    # Execute query in thread
    def _execute_sync():
        results = list(collection.find(formatted_filter))
        # Convert ObjectId to string for serialization
        for doc in results:
            if '_id' in doc:
                doc['_id'] = str(doc['_id'])
        return results
    
    try:
        results = await asyncio.to_thread(_execute_sync)
        await publish_log(f"[ACTIONS] MongoDB query executed successfully ({len(results)} docs)")
        return {
            "query_result": results,
            "doc_count": len(results)
        }
    except Exception as e:
        raise RuntimeError(f"MongoDB query failed: {e}") from e


async def _execute_redis_query(cfg: ActionConfig, inputs: Dict[str, Any]) -> Dict[str, Any]:
    """Execute a Redis query (placeholder for future implementation)"""
    raise NotImplementedError("Redis data source not yet implemented")


async def _execute_pipeline_step(
    step: Dict[str, Any],
    context: Dict[str, Any],
    step_idx: int,
    default_credential_ref: Optional[str] = None,
    default_db_config_file: Optional[str] = None,
    workspace_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Execute a single pipeline step and return the outputs to be merged into context.
    Returns dict with output_key -> value mappings.
    """
    step_type = step.get("type")
    step_name = step.get("name", f"step_{step_idx}")
    error_prefix = f"Pipeline step {step_idx} ({step_name})"

    if step_type == "query":
        # Execute a data query step
        source = step.get("source")
        if not source:
            raise ValueError(f"Pipeline step {step_idx} ({step_name}): 'query' type requires 'source'")
        credential_ref = step.get("credential_ref") or default_credential_ref
        if not credential_ref:
            raise ValueError(
                f"Pipeline step {step_idx} ({step_name}): 'query' type requires 'credential_ref' "
                f"to enforce secure connections"
            )
        db_config_file = step.get("db_config_file") or default_db_config_file
        
        # Create temporary ActionConfig for the query
        query_cfg = ActionConfig(
            type=ActionType.DATA_QUERY,
            source=source,
            query=step.get("query"),
            collection=step.get("collection"),
            filter=step.get("filter"),
            credential_ref=credential_ref,
            db_config_file=db_config_file,
        )
        result = await _execute_data_query(query_cfg, context)
        
        # Store result in context
        output_key = step.get("output", "result")
        await publish_log(f"[ACTIONS] Pipeline step {step_idx} ({step_name}): query completed")
        # return {output_key: result.get("query_result", result)}
        return _apply_output_spec(output_key, result.get("query_result", result), error_prefix=error_prefix)
        
    elif step_type == "transform":
        # Apply transformation function
        func_name = step.get("function")
        if not func_name:
            raise ValueError(f"Pipeline step {step_idx} ({step_name}): 'transform' type requires 'function'")
        
        # Load transformation function
        if func_name in _ACTION_FUNCTION_REGISTRY:
            transform_func = _ACTION_FUNCTION_REGISTRY[func_name]
        else:
            raise ValueError(f"Transform function '{func_name}' not found in registry")
        
        # Get inputs for transform
        input_keys = step.get("inputs", [])
        transform_inputs = {key: context.get(key) for key in input_keys}
        
        # Execute transform
        if asyncio.iscoroutinefunction(transform_func):
            transform_result = await transform_func(**transform_inputs)
        else:
            transform_result = await asyncio.to_thread(transform_func, **transform_inputs)
        
        # Store result
        output_key = step.get("output", "result")
        await publish_log(f"[ACTIONS] Pipeline step {step_idx} ({step_name}): transform completed")
        # return {output_key: transform_result}
        return _apply_output_spec(output_key, transform_result, error_prefix=error_prefix)
        
    elif step_type == "merge":
        # Merge multiple inputs
        input_keys = step.get("inputs", [])
        if len(input_keys) < 2:
            raise ValueError(f"Pipeline step {step_idx} ({step_name}): 'merge' requires at least 2 inputs")
        
        merged = {}
        for key in input_keys:
            if key in context:
                merged[key] = context[key]
        
        output_key = step.get("output", "merged")
        await publish_log(f"[ACTIONS] Pipeline step {step_idx} ({step_name}): merge completed")
        # return {output_key: merged}
        return _apply_output_spec(output_key, merged, error_prefix=error_prefix)

        
    elif step_type == "skill":
        # Invoke another skill (typically LLM) with current context
        skill_name = step.get("skill")
        if not skill_name:
            raise ValueError(f"Pipeline step {step_idx} ({step_name}): 'skill' type requires 'skill' field")
        
        # Find the skill in registry
        registry = get_skill_registry_for_workspace(workspace_id)
        skill = next((s for s in registry if s.name == skill_name), None)
        if not skill:
            raise ValueError(f"Skill '{skill_name}' not found in registry")
        
        # Get inputs for the skill
        input_keys = step.get("inputs", [])
        skill_inputs = {}
        for key in input_keys:
            if key in context:
                skill_inputs[key] = context[key]
            else:
                await publish_log(f"[ACTIONS] Warning: Input '{key}' not found in context for skill '{skill_name}'")
        
        await publish_log(f"[ACTIONS] Pipeline step {step_idx} ({step_name}): invoking skill '{skill_name}'")
        
        # Execute the skill using the core executor (reuses all existing execution logic!)
        # Create a minimal state for the skill execution
        minimal_state = {
            "data_store": context,
            "history": [],
            "active_skill": skill_name,
            "layman_sop": "Pipeline execution"
        }
        skill_result = await _execute_skill_core(skill, skill_inputs, minimal_state)
        
        await publish_log(f"[ACTIONS] Pipeline step {step_idx} ({step_name}): skill '{skill_name}' completed, produced: {list(skill_result.keys())}")
        # Skill results are already properly keyed, return as-is
        return skill_result
    
    elif step_type == "parallel":
        # Execute multiple steps in parallel
        parallel_steps = step.get("steps", [])
        if not parallel_steps:
            raise ValueError(f"Pipeline step {step_idx} ({step_name}): 'parallel' requires 'steps' list")
        
        await publish_log(f"[ACTIONS] Pipeline step {step_idx} ({step_name}): executing {len(parallel_steps)} steps in parallel")
        
        # Track start time for performance logging
        import time
        start_time = time.time()
        
        # Execute all parallel steps concurrently
        parallel_tasks = [
            _execute_pipeline_step(
                substep,
                context,
                f"{step_idx}.{sub_idx}",
                default_credential_ref=default_credential_ref,
                default_db_config_file=default_db_config_file,
                workspace_id=workspace_id,
            )
            for sub_idx, substep in enumerate(parallel_steps)
        ]
        
        # Wait for all to complete
        parallel_results = await asyncio.gather(*parallel_tasks)
        
        # Merge all outputs into a single dict (auto-merge at top level)
        merged_outputs = {}
        for result_dict in parallel_results:
            merged_outputs.update(result_dict)
        
        elapsed = time.time() - start_time
        await publish_log(
            f"[ACTIONS] Pipeline step {step_idx} ({step_name}): parallel execution completed in {elapsed:.2f}s, "
            f"produced: {list(merged_outputs.keys())}"
        )
        
        return merged_outputs
        
    else:
        raise ValueError(f"Pipeline step {step_idx} ({step_name}): unknown type '{step_type}'")


def _apply_output_spec(output_spec: Any, value: Any, *, error_prefix: str) -> Dict[str, Any]:
    """
    Map a produced value into one or more output keys.

    - output: "key" -> {"key": value}
    - output: ["k1","k2"] with value as (list/tuple) -> {"k1": value[0], "k2": value[1]}
    - output: ["k1","k2"] with value as dict containing keys -> {"k1": value["k1"], "k2": value["k2"]}
    """
    if output_spec is None:
        return {"result": value}
    if isinstance(output_spec, str):
        return {output_spec: value}
    if isinstance(output_spec, (list, tuple)):
        keys = [str(k) for k in output_spec]
        if len(keys) == 1:
            return {keys[0]: value}
        if isinstance(value, dict):
            missing = [k for k in keys if k not in value]
            if missing:
                raise ValueError(f"{error_prefix}: output keys {missing} not present in produced dict")
            return {k: value[k] for k in keys}
        if isinstance(value, (list, tuple)):
            if len(value) != len(keys):
                raise ValueError(
                    f"{error_prefix}: output key count ({len(keys)}) does not match produced sequence length ({len(value)})"
                )
            return {k: value[i] for i, k in enumerate(keys)}
        raise ValueError(
            f"{error_prefix}: output is a list but produced value is {type(value)}; expected dict, list, or tuple"
        )
    raise ValueError(f"{error_prefix}: 'output' must be a string or list of strings, got {type(output_spec)}")

async def _execute_data_pipeline(cfg: ActionConfig, inputs: Dict[str, Any]) -> Dict[str, Any]:
    """Execute multi-step data pipeline with support for parallel execution"""
    if not cfg.steps:
        raise ValueError("data_pipeline action requires 'steps' field")
    
    context = dict(inputs)
    await publish_log(f"[ACTIONS] Starting data pipeline with {len(cfg.steps)} steps")
    
    for step_idx, step in enumerate(cfg.steps):
        # Execute step and get outputs
        step_outputs = await _execute_pipeline_step(
            step,
            context,
            step_idx,
            default_credential_ref=cfg.credential_ref,
            default_db_config_file=cfg.db_config_file,
            workspace_id=workspace_id,
        )
        
        # Merge outputs into context (auto-merge at top level)
        context.update(step_outputs)
    
    # Return only the outputs, not the entire context
    # Filter to only new keys added during pipeline
    output_keys = set(context.keys()) - set(inputs.keys())
    return {key: context[key] for key in output_keys}


async def _execute_script(cfg: ActionConfig, inputs: Dict[str, Any]) -> Dict[str, Any]:
    """Execute external script"""
    if not cfg.script_path:
        raise ValueError("script action requires 'script_path' field")
    
    script_path = Path(cfg.script_path)
    if not script_path.exists():
        raise FileNotFoundError(f"Script not found: {script_path}")
    
    # Prepare input as JSON
    input_json = json.dumps(inputs)
    
    # Execute script
    await publish_log(f"[ACTIONS] Executing script: {script_path}")
    
    def _run_script():
        result = subprocess.run(
            [cfg.interpreter, str(script_path)],
            input=input_json,
            capture_output=True,
            text=True,
            timeout=cfg.timeout
        )
        return result
    
    try:
        result = await asyncio.to_thread(_run_script)
        
        if result.returncode != 0:
            raise RuntimeError(f"Script failed with exit code {result.returncode}: {result.stderr}")
        
        # Parse output as JSON
        try:
            output = json.loads(result.stdout)
        except json.JSONDecodeError as e:
            raise RuntimeError(f"Script output is not valid JSON: {e}\nOutput: {result.stdout}") from e
        
        if not isinstance(output, dict):
            raise ValueError(f"Script must output a JSON object, got {type(output)}")
        
        await publish_log(f"[ACTIONS] Script executed successfully")
        return output
        
    except subprocess.TimeoutExpired:
        raise RuntimeError(f"Script timed out after {cfg.timeout} seconds")
    except Exception as e:
        raise RuntimeError(f"Script execution failed: {e}") from e


async def _execute_http_call(cfg: ActionConfig, inputs: Dict[str, Any]) -> Dict[str, Any]:
    """Execute HTTP call (simpler than REST executor - synchronous)"""
    if not cfg.url:
        raise ValueError("http_call action requires 'url' field")
    
    # Format URL with input context
    url = _format_with_ctx(cfg.url, inputs)
    method = (cfg.method or "GET").upper()
    
    await publish_log(f"[ACTIONS] HTTP {method} call to {url}")
    
    try:
        async with httpx.AsyncClient(timeout=cfg.timeout, follow_redirects=True) as client:
            response = await client.request(
                method,
                url,
                json=inputs if method in ["POST", "PUT", "PATCH"] else None,
                headers=cfg.headers
            )
            response.raise_for_status()
            
            # Parse response
            content_type = response.headers.get("content-type", "")
            if "application/json" in content_type.lower():
                result = response.json()
            else:
                result = {"response": response.text}
            
            await publish_log(f"[ACTIONS] HTTP call completed (status: {response.status_code})")
            
            # Ensure result is a dict
            if not isinstance(result, dict):
                return {"response": result}
            return result
            
    except httpx.HTTPStatusError as e:
        raise RuntimeError(f"HTTP call failed with status {e.response.status_code}: {e}") from e
    except Exception as e:
        raise RuntimeError(f"HTTP call failed: {e}") from e


# Load registry from markdown at import time, then merge with database skills
SKILL_REGISTRY = load_skill_registry()

# Try to load and merge database skills
try:
    from skill_manager import load_skills_from_database
    from pydantic import ValidationError
    
    db_skill_dicts = load_skills_from_database()
    db_skills = []
    for skill_dict in db_skill_dicts:
        try:
            skill = Skill(**skill_dict)
            db_skills.append(skill)
        except ValidationError as e:
            print(f"[SKILL_DB] Warning: Invalid database skill '{skill_dict.get('name')}': {e}")
    
    # Merge database skills (override filesystem if name conflicts)
    if db_skills:
        skill_map = {s.name: s for s in SKILL_REGISTRY}
        for db_skill in db_skills:
            skill_map[db_skill.name] = db_skill
        SKILL_REGISTRY = list(skill_map.values())
        print(f"[ENGINE] Loaded {len(SKILL_REGISTRY)} total skills ({len(SKILL_REGISTRY) - len(db_skills)} filesystem, {len(db_skills)} database)")
except Exception as e:
    print(f"[ENGINE] Warning: Failed to load database skills: {e}")
    print(f"[ENGINE] Loaded {len(SKILL_REGISTRY)} skills from filesystem only")


def get_skill_registry_for_workspace(workspace_id: Optional[str]) -> List[Skill]:
    """
    Filter skills for a workspace, allowing public and workspace-specific skills.
    Filesystem skills are treated as public (workspace_id=None, is_public=True).
    """
    if workspace_id is None:
        return SKILL_REGISTRY
    return [
        s
        for s in SKILL_REGISTRY
        if s.workspace_id is None or s.workspace_id == workspace_id or s.is_public
    ]

# --- 3. NODES ---

async def autonomous_planner(state: AgentState):
    await publish_log(f"\n[PLANNER] Assessing state. Current data: {list(state['data_store'].keys())}")
    
    workspace_id = state.get("workspace_id")
    current_keys = _available_keys(state["data_store"])
    pending_rest = _rest_pending(state["data_store"])
    workspace_registry = get_skill_registry_for_workspace(workspace_id)

    # Check if workflow has failed - if so, go directly to END
    data_store = state.get("data_store", {})
    if data_store.get("_status") == "failed":
        failed_skill = data_store.get("_failed_skill", "unknown")
        error = data_store.get("_error", "Unknown error")
        await publish_log(f"[PLANNER] Workflow failed at {failed_skill}: {error}")
        await publish_log(f"[PLANNER] Reached END. Execution failed.")
        return {
            "active_skill": "END",
            "history": [f"Workflow ended due to failure in {failed_skill}"],
            "data_store": data_store
        }

    # Guardrail: if any REST skill is pending, do not plan new work. Wait for callback.
    if pending_rest:
        await publish_log(f"[PLANNER] REST work in flight {pending_rest}. Pausing planning until callback.")
        # Signal the graph to stop here; callback will resume and re-enter planner.
        return {"active_skill": "END", "history": [f"Waiting for REST callback: {sorted(pending_rest)}"]}

    completed = _completed_skills(state.get("history", []))
    runnable = [s for s in workspace_registry if s.requires.issubset(current_keys)]
    runnable = [s for s in runnable if s.name not in pending_rest]
    
    # Allow reruns when outputs are missing; skip only if already completed AND outputs are present
    runnable = [
        s for s in runnable
        if not (s.name in completed and s.produces.issubset(current_keys))
    ]
    
    # Map missing requirements to runnable skills that can provide them.
    missing_requirements: Dict[str, Set[str]] = {}
    for skill in workspace_registry:
        if skill.produces.issubset(current_keys):
            continue
        missing = skill.requires - current_keys
        for req in missing:
            # Only mandatory outputs qualify as providers
            providers = {s.name for s in runnable if req in s.produces}
            if providers:
                missing_requirements.setdefault(req, set()).update(providers)
    
    def _caps(s: Skill) -> str:
        opt = f" Optional {s.optional_produces}" if s.optional_produces else ""
        return f"- {s.name}: Provides {s.produces}.{opt} (Needs {s.requires})"
    capabilities = "\n".join([_caps(s) for s in workspace_registry])
    unblockers = sorted({name for providers in missing_requirements.values() for name in providers})
    summary_lines = _progress_summary(state)
    
    prompt = f"""
    GOAL: {state['layman_sop']}
    DATA_STORE: {json.dumps(state['data_store'])}
    PROGRESS: {summary_lines}
    
    CAPABILITIES:
    {capabilities}
    
    READY_TO_RUN: {[s.name for s in runnable]}
    UNBLOCKERS: {unblockers}  # Only skills here can supply missing requirements right now.
    
    RULES:
    - You MUST pick only from READY_TO_RUN or UNBLOCKERS.
    - If both lists are empty, return 'END'.
    - Never select a skill whose required inputs are not already in DATA_STORE.
    
    Pick the next agent. If the goal is met or no further action possible, return 'END'.
    """
    
    llm = _structured_llm(PlannerDecision, temperature=0)
    decision = await llm.ainvoke(prompt)
    
    allowed_choices = {s.name for s in runnable} | set(unblockers)
    if decision.next_agent not in allowed_choices and decision.next_agent != "END":
        # Enforce guardrail: pick a valid skill deterministically.
        fallback = next(iter([s.name for s in runnable]), None) or next(iter(unblockers), None) or "END"
        await publish_log(f"[PLANNER] Invalid choice '{decision.next_agent}'. Falling back to '{fallback}'.")
        chosen = fallback
        reason = f"Guardrail override. LLM picked invalid skill; chose {fallback} instead."
    else:
        chosen = decision.next_agent
        reason = decision.reasoning
    
    await publish_log(f"[PLANNER] Decision: {chosen} | Reasoning: {reason}")
    return {"active_skill": chosen, "history": [f"Planner chose {chosen}"]}

async def _execute_skill_core(skill_meta: Skill, input_ctx: Dict[str, Any], state: AgentState) -> Dict[str, Any]:
    """
    Core skill execution logic - reusable from both executor node and pipelines.
    Returns a dict with the skill's outputs.
    """
    workspace_id = state.get("workspace_id")

    # REST executor path
    if skill_meta.executor == "rest":
        # REST skills need full state for callback handling
        result = await _execute_rest_skill(skill_meta, state, input_ctx)
        # Extract outputs from result for pipeline use
        if "data_store" in result:
            outputs = {}
            for key in skill_meta.produces:
                if key in result["data_store"]:
                    outputs[key] = result["data_store"][key]
            return outputs
        return {}
    
    # ACTION executor path
    if skill_meta.executor == "action":
        # Actions return outputs directly
        if not skill_meta.action:
            raise RuntimeError(f"{skill_meta.name} is missing action configuration.")
        
        action_cfg = skill_meta.action
        await publish_log(f"[EXECUTOR] Running action {skill_meta.name} (type: {action_cfg.type.value})")
        
        # Execute based on action type
        if action_cfg.type == ActionType.PYTHON_FUNCTION:
            result = await _execute_python_function(action_cfg, input_ctx, state)
        elif action_cfg.type == ActionType.DATA_QUERY:
            result = await _execute_data_query(action_cfg, input_ctx)
        elif action_cfg.type == ActionType.DATA_PIPELINE:
            result = await _execute_data_pipeline(action_cfg, input_ctx, workspace_id)
        elif action_cfg.type == ActionType.SCRIPT:
            result = await _execute_script(action_cfg, input_ctx)
        elif action_cfg.type == ActionType.HTTP_CALL:
            result = await _execute_http_call(action_cfg, input_ctx)
        else:
            raise ValueError(f"Unknown action type: {action_cfg.type}")
        
        # Validate result is a dict
        if not isinstance(result, dict):
            raise ValueError(f"Action {skill_meta.name} must return a dict, got {type(result)}")
        
        # Map result keys to skill's produces field
        mapped_result = {}
        produces_list = list(skill_meta.produces)
        
        if len(produces_list) == 1:
            # Single produces key: store entire result under it
            # if it is datapipeline result, then ensure the single key is mapped to the result key
            if action_cfg.type == ActionType.DATA_PIPELINE:
                # matched_key = None
                if produces_list[0] in result.keys():
                    mapped_result[produces_list[0]] = result[produces_list[0]]
                    await publish_log(f"[EXECUTOR] Stored entire result under '{produces_list[0]}'")
                else:
                    await publish_log(
                        f"[EXECUTOR] Critical Warning: Skill {skill_meta.name} declares produces '{produces_list[0]}' "
                        f"but action did not return it"
                    )
                    raise ValueError(f"Critical Error: Missing expected key: {produces_list[0]}")
                
                # for pipe_result_key in result.keys():
                #     # matched_key = pipe_result_key
                #     mapped_result[pipe_result_key] = result[pipe_result_key]
                #     await publish_log(f"[EXECUTOR] Stored entire result under '{pipe_result_key}'")
                # else:
                #     mapped_result[produces_list[0]] = result
                #     await publish_log(f"[EXECUTOR] Stored entire result under '{produces_list[0]}'")
                    
                return mapped_result
            
                # target_key = list(result.keys())[0]
                # if target_key not in produces_list:
                #     await publish_log(
                #         f"[EXECUTOR] [Pipeline Parser] Warning: Extra key '{target_key}' not in produces list, ignored."
                #     )
                #     return mapped_result
                # mapped_result[target_key] = result[target_key]
                # await publish_log(f"[EXECUTOR] Stored entire result under '{target_key}'")
            else:
                target_key = produces_list[0]
                mapped_result[target_key] = result
                await publish_log(f"[EXECUTOR] Stored entire result under '{target_key}'")
                
        else:
            # Multiple produces keys: map by key (no positional remapping).
            # - Copy values for declared produces keys when present.
            # - Warn on missing produces keys.
            # - Append any remaining result keys unchanged (in original result order).
            if len(produces_list) == 0:
                mapped_result = dict(result)
            else:
                result_keys = list(result.keys())
                remaining_keys = set(result_keys)
                missing_expected_keys = set()

                for target_key in produces_list:
                    if target_key in result:
                        mapped_result[target_key] = result[target_key]
                        remaining_keys.discard(target_key)
                    else:
                        missing_expected_keys.add(target_key)
                        await publish_log(
                            f"[EXECUTOR] Critical Warning: Skill {skill_meta.name} declares produces '{target_key}' "
                            f"but action did not return it"
                        )
                    
                        
                # we need to end the loop as an error and not continue as keys missing will fault future errors
                # we did not end immediately above as we want all missing keys to be printed to user first.
                if missing_expected_keys:
                    raise ValueError(
                        f"Critical Error: Missing expected keys: {missing_expected_keys}"
                    )
                    

                for result_key in result_keys:
                    if result_key in remaining_keys:
                        # mapped_result[result_key] = result[result_key]
                        await publish_log(
                            f"[EXECUTOR] Warning: Extra key '{result_key}' not in produces list, ignored."
                        )
        
        await publish_log(f"[EXECUTOR] Action {skill_meta.name} completed. Results: {list(mapped_result.keys())}")
        return mapped_result
    
    # LLM executor path
    def _field_name(path: str) -> str:
        return path.replace(".", "__")

    fields = { _field_name(k): (Any, Field(..., alias=k)) for k in skill_meta.produces }
    for opt in skill_meta.optional_produces:
        fields[_field_name(opt)] = (Optional[Any], Field(default=None, alias=opt))

    DynamicModel = create_model(
        "Output",
        __config__=ConfigDict(populate_by_name=True),
        **fields,
    )

    llm = _structured_llm(DynamicModel)

    # Simulate processing
    await asyncio.sleep(1)

    prompt_text = skill_meta.prompt or f"Process this input to produce: {', '.join(sorted(skill_meta.produces))}."
    system_prompt = skill_meta.system_prompt
    tool_hint = (
        "You may call the `http_request` tool for standard REST API calls during this skill. "
        "This tool is for agent-level lookups and must not be confused with the skill-level REST executor used for agent-to-agent callbacks."
    )

    base_messages: List[BaseMessage] = [
        SystemMessage(
            content=(
                "Application rule: Do NOT invoke any tools (including http_request REST calls) "
                "unless the user or system explicitly instructs or approves it. If not explicitly told, "
                "solve without tools."
            )
        )
    ]
    if system_prompt:
        base_messages.append(SystemMessage(content=system_prompt))
    
    # Use layman_sop from state if available (for node execution), otherwise skip it (for pipeline execution)
    context_str = state.get("layman_sop", "N/A") if state else "N/A"
    
    # Properly serialize input context for LLM (especially important for complex nested data from queries)
    input_serialized = _safe_serialize(input_ctx, limit=5000)
    
    base_messages.append(
        HumanMessage(
            content=(
                f"{prompt_text}\nContext: {context_str}\nInput: {input_serialized}\n\n"
                f"{tool_hint}"
            )
        )
    )

    tool_runs, tool_history = await _run_agent_tools(base_messages)

    extraction_prompt = (
        f"Use the available inputs and any tool results to populate the structured outputs "
        f"{sorted(skill_meta.produces | skill_meta.optional_produces)}. "
        "Return only the structured fields defined by the schema."
    )
    if tool_runs:
        extraction_prompt += f"\nTool runs (standard REST agent tools): {_safe_serialize(tool_runs, limit=2000)}"

    final_messages = tool_history + [HumanMessage(content=extraction_prompt)]

    result = await llm.ainvoke(final_messages)
    
    # The result from with_structured_output() is the Pydantic model itself, not a BaseMessage
    if not result:
        raise RuntimeError(f"{skill_meta.name}: Failed to extract structured output from LLM.")

    # Extract outputs from the Pydantic model
    outputs = {}
    for k in skill_meta.produces:
        field_alias = _field_name(k)
        val = getattr(result, field_alias, None)
        if val is not None:
            outputs[k] = val
    for k in skill_meta.optional_produces:
        field_alias = _field_name(k)
        val = getattr(result, field_alias, None)
        if val is not None:
            outputs[k] = val

    await publish_log(f"[EXECUTOR] {skill_meta.name} finished. Results: {_safe_serialize(outputs, limit=500)}")
    return outputs


async def skilled_executor(state: AgentState):
    skill_name = state["active_skill"]
    workspace_id = state.get("workspace_id")
    registry = get_skill_registry_for_workspace(workspace_id)
    skill_meta = next(s for s in registry if s.name == skill_name)

    await publish_log(f"[EXECUTOR] Running {skill_name}...")
    
    # Track execution sequence for loop detection
    execution_sequence = state.get("execution_sequence") or []
    execution_sequence.append(skill_name)
    
    # Check for infinite loops BEFORE executing
    loop_error = _detect_infinite_loop(execution_sequence)
    if loop_error:
        await publish_log(f"[EXECUTOR] 🚨 {loop_error}")
        await publish_log(f"[EXECUTOR] Execution sequence: {' -> '.join(execution_sequence[-10:])}")
        
        # Mark workflow as failed due to infinite loop
        updated_store = state["data_store"]
        updated_store["_error"] = loop_error
        updated_store["_failed_skill"] = skill_name
        updated_store["_status"] = "failed"
        
        return {
            "data_store": updated_store,
            "execution_sequence": execution_sequence,
            "history": [f"INFINITE LOOP DETECTED: {loop_error}"],
            "active_skill": "END"  # Force workflow to end
        }

    present_keys = _available_keys(state["data_store"])
    missing_inputs = {req for req in skill_meta.requires if req not in present_keys}
    if missing_inputs:
        missing_list = ", ".join(sorted(missing_inputs))
        raise RuntimeError(f"{skill_name} cannot run. Missing required inputs: {missing_list}")

    input_ctx = {k: _get_path_value(state["data_store"], k) for k in skill_meta.requires}

    try:
        # Use core execution logic
        outputs = await _execute_skill_core(skill_meta, input_ctx, state)
        
        # Merge outputs into data_store
        updated_store = state["data_store"]
        for path, val in outputs.items():
            updated_store = _set_path_value(updated_store, path, val)
        
        return {
            "data_store": updated_store,
            "execution_sequence": execution_sequence,
            "history": [f"Executed {skill_meta.name} ({skill_meta.executor})"],
            "active_skill": None  # Clear active skill to allow planner to continue
        }
        
    except Exception as exc:
        error_msg = str(exc)
        await publish_log(f"[EXECUTOR] Skill {skill_meta.name} failed: {error_msg}")
        
        # Return error state and force workflow to END
        updated_store = state["data_store"]
        updated_store["_error"] = error_msg
        updated_store["_failed_skill"] = skill_meta.name
        updated_store["_status"] = "failed"
        
        return {
            "data_store": updated_store,
            "execution_sequence": execution_sequence,
            "history": [f"Skill {skill_meta.name} failed: {error_msg}"],
            "active_skill": "END"  # Force workflow to end
        }


def route_post_exec(state: AgentState):
    skill_name = state["active_skill"]
    
    # Handle None or missing active_skill (can happen during callback updates)
    if not skill_name:
        emit_log("[ROUTER] No active skill, routing to planner.")
        return "planner"
    
    # Find the skill metadata safely
    workspace_id = state.get("workspace_id")
    registry = get_skill_registry_for_workspace(workspace_id)
    skill_meta = next((s for s in registry if s.name == skill_name), None)
    if not skill_meta:
        emit_log(f"[ROUTER] Unknown skill '{skill_name}', routing to planner.")
        return "planner"
    
    if skill_meta.executor == "rest":
        emit_log(f"[ROUTER] REST executor for {skill_name}. Waiting for callback.")
        return "await_callback"
    
    if skill_meta.hitl_enabled:
        emit_log(f"[ROUTER] HITL enabled for {skill_name}. Redirecting to HUMAN_REVIEW.")
        return "human_review"
    return "planner"

# --- 4. GRAPH SETUP ---
workflow = StateGraph(AgentState)
workflow.add_node("planner", autonomous_planner)
workflow.add_node("executor", skilled_executor)
workflow.add_node("human_review", lambda x: x) # Passive node for interruption
workflow.add_node("await_callback", lambda x: x) # Passive node for REST callbacks

workflow.set_entry_point("planner")

def planner_route(state):
    if state["active_skill"] == "END" or not state["active_skill"]:
        emit_log("[PLANNER] Reached END. Execution completed.")
        return END
    
    last_skill = _last_executed(state.get("history", []))
    if last_skill and state["active_skill"] == last_skill:
        emit_log(f"[PLANNER] {state['active_skill']} was just executed. Routing to HUMAN_REVIEW to avoid repetition.")
        return "human_review"
    
    return "executor"

workflow.add_conditional_edges("planner", planner_route)
workflow.add_conditional_edges("executor", route_post_exec, {
    "human_review": "human_review",
    "await_callback": "await_callback",
    "planner": "planner"
})
workflow.add_edge("human_review", "planner")
workflow.add_edge("await_callback", "planner")

class _AsyncPostgresSaver(PostgresSaver):
    """
    Thin async wrapper around the sync PostgresSaver.
    Uses a thread to avoid blocking the event loop while keeping DB persistence.
    """

    def _notify(self, payload: Dict[str, Any]):
        """Send notification via pub/sub client; best-effort (errors are logged, not raised)."""
        try:
            pubsub = get_pubsub_client()
            pubsub.publish('run_events', payload)
        except Exception as exc:  # pragma: no cover - defensive
            emit_log(f"[CHECKPOINTER] Failed to publish run_events: {exc}")

    async def aget_tuple(self, config):
        return await asyncio.to_thread(super().get_tuple, config)

    def put(self, config, checkpoint, metadata, new_versions):
        result = super().put(config, checkpoint, metadata, new_versions)
        thread_id = config.get("configurable", {}).get("thread_id")
        payload = {
            "thread_id": thread_id,
            "checkpoint_id": checkpoint.get("id"),
            "checkpoint_ns": config.get("configurable", {}).get("checkpoint_ns", ""),
            "metadata": metadata,
        }
        self._notify(payload)
        return result

    async def alist(self, config, *, filter=None, before=None, limit=None):
        def _list_sync():
            return list(PostgresSaver.list(self, config, filter=filter, before=before, limit=limit))
        
        items = await asyncio.to_thread(_list_sync)
        for item in items:
            yield item

    async def aput(self, config, checkpoint, metadata, new_versions):
        result = await asyncio.to_thread(
            super().put, config, checkpoint, metadata, new_versions
        )
        thread_id = config.get("configurable", {}).get("thread_id")
        payload = {
            "thread_id": thread_id,
            "checkpoint_id": checkpoint.get("id"),
            "checkpoint_ns": config.get("configurable", {}).get("checkpoint_ns", ""),
            "metadata": metadata,
        }
        await asyncio.to_thread(self._notify, payload)
        return result

    async def aput_writes(self, config, writes, task_id, task_path=""):
        return await asyncio.to_thread(
            super().put_writes, config, writes, task_id, task_path
        )

    async def adelete_thread(self, thread_id):
        await asyncio.to_thread(super().delete_thread, thread_id)


def _use_postgres_checkpointer() -> bool:
    flag = os.getenv("USE_POSTGRES_CHECKPOINTS", "true").lower()
    return flag in {"1", "true", "yes", "on"}


def _build_checkpointer():
    """
    Create the checkpointer using the centralized connection pool.
    Postgres Saver is sync-only; we adapt it for async usage to avoid event loop blocking.
    """
    if not _use_postgres_checkpointer():
        emit_log("[CHECKPOINTER] Using in-memory checkpoints (Postgres disabled).")
        return MemorySaver()

def _build_checkpointer():
    """
    Build checkpointer based on environment configuration.
    
    Options:
    1. USE_POSTGRES_CHECKPOINTS=true: Direct PostgreSQL (slow, causes bottleneck)
    2. USE_POSTGRES_CHECKPOINTS=false: Buffered Redis + PostgreSQL (RECOMMENDED)
       - Fast execution with Redis buffering
       - Batch writes to PostgreSQL on completion
       - 30-minute TTL with incremental extension
    """
    # Ensure env files are loaded before reading DATABASE_URL
    load_env_once(Path(__file__).resolve().parent)
    
    use_postgres = _get_env_value("USE_POSTGRES_CHECKPOINTS", "false").lower() == "true"
    
    if use_postgres:
        # Direct PostgreSQL checkpointing (legacy mode)
        emit_log("[CHECKPOINTER] Using direct PostgreSQL checkpointing (may cause performance issues)")
        
        DB_URI = _get_env_value("DATABASE_URL", "")
        if not DB_URI:
            raise ValueError("DB_URI is not set")

        try:
            # Initialize centralized connection pools
            init_connection_pools()
            
            # Get shared Postgres pool
            pool = get_postgres_pool()
            
            checkpointer = _AsyncPostgresSaver(pool)
            checkpointer.setup()
            emit_log("[CHECKPOINTER] Postgres checkpointer initialized with shared pool.")
            
            # Initialize log persistence with shared pool
            _init_log_persistence_from_pool(pool)
            
            return checkpointer
        except Exception as exc:
            emit_log(f"[CHECKPOINTER] Postgres checkpointer unavailable; falling back to memory. Reason: {exc}")
            return MemorySaver()
    else:
        # Buffered mode: Redis + PostgreSQL (RECOMMENDED)
        emit_log("[CHECKPOINTER] Using buffered checkpointing (Redis + PostgreSQL)")
        
        try:
            from services.buffered_saver import BufferedCheckpointSaver
            
            checkpointer = BufferedCheckpointSaver()
            emit_log("[CHECKPOINTER] ✅ Buffered checkpointer initialized (Memory + Redis buffer)")
            
            # Initialize log persistence if PostgreSQL is available
            DB_URI = _get_env_value("DATABASE_URL", "")
            if DB_URI:
                try:
                    init_connection_pools()
                    pool = get_postgres_pool()
                    _init_log_persistence_from_pool(pool)
                except Exception as exc:
                    emit_log(f"[LOG_PERSIST] Failed to initialize log persistence: {exc}")
            
            return checkpointer
            
        except Exception as exc:
            emit_log(f"[CHECKPOINTER] Buffered checkpointer unavailable; falling back to memory. Reason: {exc}")
            return MemorySaver()


def _init_log_persistence_from_pool(pool: ConnectionPool):
    """Initialize log persistence using the shared connection pool (Windows compatible)."""
    try:
        # Use the same shared pool for log persistence
        set_db_pool(pool)
        emit_log("[LOG_PERSIST] Log persistence initialized with shared pool.")
    except Exception as exc:
        emit_log(f"[LOG_PERSIST] Failed to initialize log persistence: {exc}")



# Compile graph with async-friendly checkpointer (Postgres if available, else Memory)
checkpointer = _build_checkpointer()
app = workflow.compile(checkpointer=checkpointer, interrupt_before=["human_review", "await_callback"])


# --- Register Pipeline Functions ---
# Auto-discover and register functions from pipeline modules
try:
    from skills.FinancialAnalysisPipeline.pipeline_functions import (
        compute_financial_metrics,
        format_financial_report,
        calculate_growth_metrics
    )
    
    # Register each function
    register_action_function("compute_financial_metrics", compute_financial_metrics)
    register_action_function("format_financial_report", format_financial_report)
    register_action_function("calculate_growth_metrics", calculate_growth_metrics)
    
    emit_log("[ACTIONS] Registered FinancialAnalysisPipeline functions")
except ImportError as e:
    emit_log(f"[ACTIONS] Warning: Could not import FinancialAnalysisPipeline functions: {e}")
except Exception as e:
    emit_log(f"[ACTIONS] Error registering FinancialAnalysisPipeline functions: {e}")