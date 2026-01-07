import os
import json
import asyncio
from pathlib import Path
from typing import Annotated, TypedDict, Union, List, Dict, Any, Set, Optional, Type
from pydantic import BaseModel, Field, ValidationError, create_model, ConfigDict
import httpx

import yaml
from langchain_openai import ChatOpenAI
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage, AIMessage, ToolMessage
from langchain_core.tools import tool
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from log_stream import publish_log, emit_log

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
    executor: str = "llm"  # "llm" (default) or "rest"
    rest: Optional[RestConfig] = None

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
        except KeyError as exc:
            raise RuntimeError(f"Missing required field {exc} in {md_file}") from exc

        if name in seen_names:
            raise RuntimeError(f"Duplicate skill name detected: {name}")

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


# --- Utilities ---
def _require_openai_api_key() -> str:
    key = os.getenv("OPENAI_API_KEY")
    if not key:
        raise RuntimeError(
            "Missing OPENAI_API_KEY. Set it in your environment or .env before running."
        )
    return key


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


async def _execute_rest_skill(skill_meta: Skill, state: AgentState, input_ctx: Dict[str, Any]):
    if not skill_meta.rest:
        raise RuntimeError(f"{skill_meta.name} is missing REST configuration.")

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


# Load registry from markdown at import time
SKILL_REGISTRY = load_skill_registry()

# --- 3. NODES ---

async def autonomous_planner(state: AgentState):
    await publish_log(f"\n[PLANNER] Assessing state. Current data: {list(state['data_store'].keys())}")
    
    current_keys = _available_keys(state["data_store"])
    pending_rest = _rest_pending(state["data_store"])

    # Guardrail: if any REST skill is pending, do not plan new work. Wait for callback.
    if pending_rest:
        await publish_log(f"[PLANNER] REST work in flight {pending_rest}. Pausing planning until callback.")
        # Signal the graph to stop here; callback will resume and re-enter planner.
        return {"active_skill": "END", "history": [f"Waiting for REST callback: {sorted(pending_rest)}"]}

    completed = _completed_skills(state.get("history", []))
    runnable = [s for s in SKILL_REGISTRY if s.requires.issubset(current_keys)]
    runnable = [s for s in runnable if s.name not in pending_rest]
    
    # Allow reruns when outputs are missing; skip only if already completed AND outputs are present
    runnable = [
        s for s in runnable
        if not (s.name in completed and s.produces.issubset(current_keys))
    ]
    
    # Map missing requirements to runnable skills that can provide them.
    missing_requirements: Dict[str, Set[str]] = {}
    for skill in SKILL_REGISTRY:
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
    capabilities = "\n".join([_caps(s) for s in SKILL_REGISTRY])
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

async def skilled_executor(state: AgentState):
    skill_name = state["active_skill"]
    skill_meta = next(s for s in SKILL_REGISTRY if s.name == skill_name)
    
    await publish_log(f"[EXECUTOR] Running {skill_name}...")
    
    present_keys = _available_keys(state["data_store"])
    missing_inputs = {req for req in skill_meta.requires if req not in present_keys}
    if missing_inputs:
        missing_list = ", ".join(sorted(missing_inputs))
        raise RuntimeError(f"{skill_name} cannot run. Missing required inputs: {missing_list}")
    
    input_ctx = {k: _get_path_value(state["data_store"], k) for k in skill_meta.requires}

    # REST executor path: fire-and-pause until callback arrives.
    if skill_meta.executor == "rest":
        return await _execute_rest_skill(skill_meta, state, input_ctx)

    # Dynamic Schema: In reality, read ## OUTPUT SCHEMA from an MD file
    # Here we simulate the fields based on skill_meta.produces
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
    
    # Simulate processing (Add a tiny delay for realism)
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
    base_messages.append(
        HumanMessage(
            content=(
                f"{prompt_text}\nContext: {state['layman_sop']}\nInput: {input_ctx}\n\n"
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
    
    output_data = result.model_dump(by_alias=True, exclude_none=True)
    updated_store = state["data_store"]
    for path, val in output_data.items():
        updated_store = _set_path_value(updated_store, path, val)

    await publish_log(f"[EXECUTOR] {skill_name} finished. Results: {output_data}")
    history_entry = [f"Executed {skill_name}"]
    if tool_runs:
        used = ", ".join(sorted({run.get("tool") or "unknown_tool" for run in tool_runs}))
        history_entry.append(f"Agent tools used: {used}")
    if skill_meta.hitl_enabled:
        history_entry.append(f"Awaiting human review for {skill_name}")
    return {
        "data_store": updated_store,
        "history": history_entry
    }

def route_post_exec(state: AgentState):
    skill_name = state["active_skill"]
    skill_meta = next(s for s in SKILL_REGISTRY if s.name == skill_name)
    
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

memory = MemorySaver()
app = workflow.compile(checkpointer=memory, interrupt_before=["human_review", "await_callback"])