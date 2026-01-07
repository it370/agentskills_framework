import os
import json
import asyncio
from pathlib import Path
from typing import Annotated, TypedDict, Union, List, Dict, Any, Set, Optional, Type
from pydantic import BaseModel, Field, ValidationError, create_model
import httpx

import yaml
from langchain_openai import ChatOpenAI
from langchain_core.messages import BaseMessage, HumanMessage
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from log_stream import publish_log, emit_log

class RestConfig(BaseModel):
    url: str
    method: str = "POST"
    headers: Dict[str, str] = Field(default_factory=dict)
    timeout: float = 15.0


# --- 1. MODELS & REGISTRY ---
class Skill(BaseModel):
    name: str
    description: str
    requires: Set[str]
    produces: Set[str]
    optional_produces: Set[str] = set()
    hitl_enabled: bool = False
    prompt: Optional[str] = None
    executor: str = "llm"  # "llm" (default) or "rest"
    rest: Optional[RestConfig] = None

class PlannerDecision(BaseModel):
    next_agent: str = Field(description="Name of agent or 'END'")
    reasoning: str = Field(description="Reasoning for the decision")

# --- Skill Loader (Markdown-based, Anthropic-style registry) ---
def _extract_frontmatter(md_text: str) -> Dict[str, Any]:
    lines = md_text.splitlines()
    if not lines or lines[0].strip() != "---":
        raise ValueError("Skill file must start with frontmatter delimited by '---'.")

    for idx in range(1, len(lines)):
        if lines[idx].strip() == "---":
            frontmatter = "\n".join(lines[1:idx])
            return yaml.safe_load(frontmatter) or {}
    raise ValueError("Skill file frontmatter must be closed with '---'.")


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
        meta = _extract_frontmatter(raw)

        prompt_text = meta.get("prompt")
        prompt_file = md_file.parent / "prompt.md"
        if prompt_file.exists():
            prompt_candidate = prompt_file.read_text(encoding="utf-8").strip()
            if prompt_candidate:
                prompt_text = prompt_candidate

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


def _available_keys(store: Dict[str, Any]) -> Set[str]:
    """
    Treat missing/empty values as unavailable. Booleans and zeros are valid.
    Strings that are None or empty/whitespace are treated as missing.
    """
    present: Set[str] = set()
    for k, v in store.items():
        if v is None:
            continue
        if isinstance(v, str) and not v.strip():
            continue
        present.add(k)
    return present


def _last_executed(history: List[str]) -> Optional[str]:
    """Return the most recent executed skill from history, if any."""
    for entry in reversed(history):
        if entry.startswith("Executed "):
            return entry.replace("Executed ", "", 1)
    return None


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

    async with httpx.AsyncClient(timeout=skill_meta.rest.timeout) as client:
        response = await client.request(
            skill_meta.rest.method,
            skill_meta.rest.url,
            json=payload,
            headers=skill_meta.rest.headers,
        )
        response.raise_for_status()

    await publish_log(f"[EXECUTOR] {skill_meta.name} dispatched to REST endpoint {skill_meta.rest.url}")
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

    runnable = [s for s in SKILL_REGISTRY if s.requires.issubset(current_keys)]
    runnable = [s for s in runnable if s.name not in pending_rest]
    
    # Check for already completed skills to avoid loops
    runnable = [s for s in runnable if not s.produces.issubset(current_keys)]
    
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
    
    prompt = f"""
    GOAL: {state['layman_sop']}
    DATA_STORE: {json.dumps(state['data_store'])}
    
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
    missing_inputs = skill_meta.requires - present_keys
    if missing_inputs:
        missing_list = ", ".join(sorted(missing_inputs))
        raise RuntimeError(f"{skill_name} cannot run. Missing required inputs: {missing_list}")
    
    input_ctx = {k: state["data_store"].get(k) for k in skill_meta.requires}

    # REST executor path: fire-and-pause until callback arrives.
    if skill_meta.executor == "rest":
        return await _execute_rest_skill(skill_meta, state, input_ctx)

    # Dynamic Schema: In reality, read ## OUTPUT SCHEMA from an MD file
    # Here we simulate the fields based on skill_meta.produces
    fields = {k: (Any, ...) for k in skill_meta.produces}
    for opt in skill_meta.optional_produces:
        fields[opt] = (Optional[Any], None)
    DynamicModel = create_model("Output", **fields)
    
    llm = _structured_llm(DynamicModel)
    
    # Simulate processing (Add a tiny delay for realism)
    await asyncio.sleep(1)
    
    # We pass the relevant data and the SOP context
    prompt_text = skill_meta.prompt or f"Process this input to produce: {', '.join(sorted(skill_meta.produces))}."
    result = await llm.ainvoke(f"{prompt_text}\nContext: {state['layman_sop']}\nInput: {input_ctx}")
    
    await publish_log(f"[EXECUTOR] {skill_name} finished. Results: {result.dict()}")
    history_entry = [f"Executed {skill_name}"]
    if skill_meta.hitl_enabled:
        history_entry.append(f"Awaiting human review for {skill_name}")
    return {
        "data_store": {**state["data_store"], **result.dict()},
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