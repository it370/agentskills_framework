from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Mapping, MutableMapping, Optional, Sequence

from admin_events import broadcast_run_event
from log_stream import emit_log


class WorkflowUiEmitter:
    """Centralized builder/emitter for workflow_ui_update events."""

    @staticmethod
    def workflow_node_kind_from_step(step_type: str) -> str:
        mapping = {
            "query": "data_query",
            "transform": "function",
            "merge": "merge",
            "skill": "composite",
            "parallel": "pipeline",
            "conditional": "conditional",
        }
        return mapping.get(step_type, "pipeline")

    @staticmethod
    def consumes_from_keys(input_keys: Sequence[str], key_sources: Mapping[str, str]) -> List[str]:
        refs: List[str] = []
        for key in input_keys:
            src = key_sources.get(key)
            if src:
                refs.append(src)
        seen = set()
        deduped: List[str] = []
        for ref in refs:
            if ref in seen:
                continue
            seen.add(ref)
            deduped.append(ref)
        return deduped

    async def emit(self, state: Mapping[str, Any], payload: Dict[str, Any]) -> None:
        """Emit UI-only workflow update to thread scoped subscribers."""
        thread_id = state.get("thread_id")
        if not thread_id:
            return
        phase = str(payload.get("phase") or "workflow_update")
        event_id = str(payload.get("event_id") or f"{thread_id}:{phase}:{datetime.utcnow().timestamp()}")
        parent_event_id = payload.get("parent_event_id")
        if parent_event_id is not None:
            parent_event_id = str(parent_event_id)
        try:
            await broadcast_run_event(
                {
                    "type": "workflow_ui_update",
                    "thread_id": thread_id,
                    "ui_target": "agentic_view",
                    "timestamp": datetime.utcnow().isoformat(),
                    "event_id": event_id,
                    "parent_event_id": parent_event_id,
                    **payload,
                }
            )
        except Exception as exc:
            emit_log(f"[WORKFLOW_UI] Failed to emit workflow_ui_update: {exc}", thread_id)

    async def emit_planner_decision(
        self,
        state: Mapping[str, Any],
        *,
        chosen: str,
        reason: str,
        available_data_keys: Sequence[str],
        ready_to_run: Sequence[str],
        unblockers: Sequence[str],
    ) -> None:
        await self.emit(
            state,
            {
                "phase": "planner_decision",
                "category": "decision",
                "source": "planner",
                "agent_name": "planner",
                "message": f"Planner chose {chosen}",
                "reasoning": reason,
                "inputs": {"available_data_keys": sorted(list(available_data_keys))},
                "outputs": {"chosen_agent": chosen},
                "rich": {
                    "json": {
                        "chosen_agent": chosen,
                        "reasoning": reason,
                        "ready_to_run": list(ready_to_run),
                        "unblockers": list(unblockers),
                    }
                },
            },
        )

    async def emit_agent_action(
        self,
        state: Mapping[str, Any],
        *,
        event_id: str,
        skill_name: str,
        node_kind: str,
        input_ctx: Mapping[str, Any],
        consumes_from: Sequence[str],
        executor: str,
        required_inputs: Sequence[str],
    ) -> None:
        await self.emit(
            state,
            {
                "event_id": event_id,
                "phase": "agent_action",
                "category": "action",
                "source": skill_name,
                "agent_name": skill_name,
                "node_kind": node_kind,
                "message": f"Executing {skill_name}",
                "inputs": dict(input_ctx),
                "outputs": {},
                "consumes_from": list(consumes_from),
                "rich": {
                    "json": {
                        "executor": executor,
                        "required_inputs": sorted(list(required_inputs)),
                    }
                },
            },
        )

    async def emit_agent_result(
        self,
        state: Mapping[str, Any],
        *,
        event_id: str,
        parent_event_id: str,
        skill_name: str,
        node_kind: str,
        input_ctx: Mapping[str, Any],
        outputs: Mapping[str, Any],
        consumes_from: Sequence[str],
    ) -> None:
        await self.emit(
            state,
            {
                "event_id": event_id,
                "parent_event_id": parent_event_id,
                "phase": "agent_result",
                "category": "result",
                "source": skill_name,
                "agent_name": skill_name,
                "node_kind": node_kind,
                "message": f"{skill_name} completed",
                "inputs": dict(input_ctx),
                "outputs": {"produced_keys": list(outputs.keys()), "result": dict(outputs)},
                "consumes_from": list(consumes_from),
                "rich": {"json": dict(outputs)},
            },
        )

    async def emit_agent_error(
        self,
        state: Mapping[str, Any],
        *,
        parent_event_id: str,
        skill_name: str,
        node_kind: str,
        input_ctx: Mapping[str, Any],
        error_msg: str,
        consumes_from: Sequence[str],
    ) -> None:
        await self.emit(
            state,
            {
                "parent_event_id": parent_event_id,
                "phase": "agent_error",
                "category": "error",
                "source": skill_name,
                "agent_name": skill_name,
                "node_kind": node_kind,
                "message": f"{skill_name} failed",
                "inputs": dict(input_ctx),
                "outputs": {"error": error_msg},
                "consumes_from": list(consumes_from),
                "rich": {"json": {"error": error_msg}},
            },
        )

    async def emit_pipeline_start(
        self,
        state: Mapping[str, Any],
        *,
        pipeline_id: str,
        step_count: int,
        inputs: Mapping[str, Any],
    ) -> None:
        await self.emit(
            state,
            {
                "event_id": f"{pipeline_id}:start",
                "phase": "pipeline_step_start",
                "node_kind": "pipeline",
                "step_type": "pipeline",
                "execution_mode": "serial",
                "pipeline_id": pipeline_id,
                "pipeline_step_id": "root",
                "message": f"Starting data pipeline ({step_count} steps)",
                "inputs": dict(inputs),
                "outputs": {},
                "consumes_from": [],
                "rich": {"json": {"step_count": step_count}},
            },
        )

    async def emit_pipeline_complete(
        self,
        state: Mapping[str, Any],
        *,
        pipeline_id: str,
        parent_event_id: Optional[str],
        inputs: Mapping[str, Any],
        outputs: Mapping[str, Any],
        output_keys: Sequence[str],
    ) -> None:
        await self.emit(
            state,
            {
                "event_id": f"{pipeline_id}:result",
                "parent_event_id": parent_event_id,
                "phase": "pipeline_step_result",
                "node_kind": "pipeline",
                "step_type": "pipeline",
                "execution_mode": "serial",
                "pipeline_id": pipeline_id,
                "pipeline_step_id": "root",
                "message": "Data pipeline completed",
                "inputs": dict(inputs),
                "outputs": dict(outputs),
                "consumes_from": [],
                "rich": {"json": {"output_keys": sorted(list(output_keys))}},
            },
        )

    async def emit_pipeline_step_start(
        self,
        state: Mapping[str, Any],
        *,
        event_id: str,
        parent_event_id: Optional[str],
        step_node_kind: str,
        step_type: str,
        execution_mode: str,
        pipeline_id: Optional[str],
        pipeline_step_id: str,
        parallel_group_id: Optional[str],
        branch_id: Optional[str],
        parallel_branch_index: Optional[int],
        parallel_branch_count: Optional[int],
        step_name: str,
        step_inputs: Mapping[str, Any],
        consumes_from: Sequence[str],
    ) -> None:
        await self.emit(
            state,
            {
                "event_id": event_id,
                "parent_event_id": parent_event_id,
                "phase": "pipeline_step_start",
                "node_kind": step_node_kind,
                "step_type": step_type,
                "execution_mode": execution_mode,
                "pipeline_id": pipeline_id,
                "pipeline_step_id": pipeline_step_id,
                "parallel_group_id": parallel_group_id,
                "branch_id": branch_id,
                "parallel_branch_index": parallel_branch_index,
                "parallel_branch_count": parallel_branch_count,
                "message": f"{step_name} started",
                "inputs": dict(step_inputs),
                "outputs": {},
                "consumes_from": list(consumes_from),
                "rich": {"json": {"step_type": step_type, "step_name": step_name}},
            },
        )

    async def emit_pipeline_step_result(
        self,
        state: Mapping[str, Any],
        *,
        event_id: str,
        parent_event_id: str,
        step_node_kind: str,
        step_type: str,
        execution_mode: str,
        pipeline_id: Optional[str],
        pipeline_step_id: str,
        parallel_group_id: Optional[str],
        branch_id: Optional[str],
        parallel_branch_index: Optional[int],
        parallel_branch_count: Optional[int],
        step_name: str,
        step_inputs: Mapping[str, Any],
        outputs: Mapping[str, Any],
        consumes_from: Sequence[str],
        skipped: bool = False,
    ) -> None:
        message = f"{step_name} skipped by condition" if skipped else f"{step_name} completed"
        rich_json: Dict[str, Any] = {"skipped": True} if skipped else dict(outputs)
        await self.emit(
            state,
            {
                "event_id": event_id,
                "parent_event_id": parent_event_id,
                "phase": "pipeline_step_result",
                "node_kind": step_node_kind,
                "step_type": step_type,
                "execution_mode": execution_mode,
                "pipeline_id": pipeline_id,
                "pipeline_step_id": pipeline_step_id,
                "parallel_group_id": parallel_group_id,
                "branch_id": branch_id,
                "parallel_branch_index": parallel_branch_index,
                "parallel_branch_count": parallel_branch_count,
                "message": message,
                "inputs": dict(step_inputs),
                "outputs": dict(outputs),
                "consumes_from": list(consumes_from),
                "rich": {"json": rich_json},
            },
        )

    async def emit_pipeline_step_error(
        self,
        state: Mapping[str, Any],
        *,
        event_id: str,
        parent_event_id: str,
        step_node_kind: str,
        step_type: str,
        execution_mode: str,
        pipeline_id: Optional[str],
        pipeline_step_id: str,
        parallel_group_id: Optional[str],
        branch_id: Optional[str],
        parallel_branch_index: Optional[int],
        parallel_branch_count: Optional[int],
        step_name: str,
        step_inputs: Mapping[str, Any],
        error: str,
        consumes_from: Sequence[str],
    ) -> None:
        await self.emit(
            state,
            {
                "event_id": event_id,
                "parent_event_id": parent_event_id,
                "phase": "pipeline_step_error",
                "node_kind": step_node_kind,
                "step_type": step_type,
                "execution_mode": execution_mode,
                "pipeline_id": pipeline_id,
                "pipeline_step_id": pipeline_step_id,
                "parallel_group_id": parallel_group_id,
                "branch_id": branch_id,
                "parallel_branch_index": parallel_branch_index,
                "parallel_branch_count": parallel_branch_count,
                "message": f"{step_name} failed",
                "inputs": dict(step_inputs),
                "outputs": {"error": error},
                "consumes_from": list(consumes_from),
                "rich": {"json": {"error": error}},
            },
        )

    async def emit_parallel_group_start(
        self,
        state: Mapping[str, Any],
        *,
        event_id: str,
        parent_event_id: str,
        pipeline_id: Optional[str],
        pipeline_step_id: str,
        parallel_group_id: str,
        step_name: str,
        group_inputs: Mapping[str, Any],
        consumes_from: Sequence[str],
        branch_count: int,
    ) -> None:
        await self.emit(
            state,
            {
                "event_id": event_id,
                "parent_event_id": parent_event_id,
                "phase": "parallel_group_start",
                "node_kind": "pipeline",
                "step_type": "parallel",
                "execution_mode": "parallel_group",
                "pipeline_id": pipeline_id,
                "pipeline_step_id": pipeline_step_id,
                "parallel_group_id": parallel_group_id,
                "message": f"{step_name}: parallel group started",
                "inputs": dict(group_inputs),
                "outputs": {},
                "consumes_from": list(consumes_from),
                "rich": {"json": {"branch_count": branch_count}},
            },
        )

    async def emit_parallel_branch_start(
        self,
        state: Mapping[str, Any],
        *,
        event_id: str,
        parent_event_id: str,
        pipeline_id: Optional[str],
        pipeline_step_id: str,
        parallel_group_id: str,
        branch_id: str,
        branch_index: int,
        branch_count: int,
    ) -> None:
        await self.emit(
            state,
            {
                "event_id": event_id,
                "parent_event_id": parent_event_id,
                "phase": "parallel_branch_start",
                "node_kind": "pipeline",
                "step_type": "parallel_branch",
                "execution_mode": "parallel",
                "pipeline_id": pipeline_id,
                "pipeline_step_id": pipeline_step_id,
                "parallel_group_id": parallel_group_id,
                "branch_id": branch_id,
                "parallel_branch_index": branch_index,
                "parallel_branch_count": branch_count,
                "message": f"Parallel branch {branch_index + 1} started",
                "inputs": {},
                "outputs": {},
                "consumes_from": [],
                "rich": {"json": {"branch_index": branch_index}},
            },
        )

    async def emit_parallel_branch_result(
        self,
        state: Mapping[str, Any],
        *,
        event_id: str,
        parent_event_id: str,
        pipeline_id: Optional[str],
        pipeline_step_id: str,
        parallel_group_id: str,
        branch_id: str,
        branch_index: int,
        branch_count: int,
        outputs: Mapping[str, Any],
    ) -> None:
        await self.emit(
            state,
            {
                "event_id": event_id,
                "parent_event_id": parent_event_id,
                "phase": "parallel_branch_result",
                "node_kind": "pipeline",
                "step_type": "parallel_branch",
                "execution_mode": "parallel",
                "pipeline_id": pipeline_id,
                "pipeline_step_id": pipeline_step_id,
                "parallel_group_id": parallel_group_id,
                "branch_id": branch_id,
                "parallel_branch_index": branch_index,
                "parallel_branch_count": branch_count,
                "message": f"Parallel branch {branch_index + 1} completed",
                "inputs": {},
                "outputs": dict(outputs),
                "consumes_from": [],
                "rich": {"json": {"output_keys": list(outputs.keys())}},
            },
        )

    async def emit_parallel_group_merge(
        self,
        state: Mapping[str, Any],
        *,
        event_id: str,
        parent_event_id: str,
        pipeline_id: Optional[str],
        pipeline_step_id: str,
        parallel_group_id: str,
        step_name: str,
        merged_outputs: Mapping[str, Any],
        branch_result_event_ids: Sequence[str],
    ) -> None:
        await self.emit(
            state,
            {
                "event_id": event_id,
                "parent_event_id": parent_event_id,
                "phase": "parallel_group_merge",
                "node_kind": "merge",
                "step_type": "parallel_merge",
                "execution_mode": "parallel_group",
                "pipeline_id": pipeline_id,
                "pipeline_step_id": pipeline_step_id,
                "parallel_group_id": parallel_group_id,
                "message": f"{step_name}: parallel branches merged",
                "inputs": {},
                "outputs": dict(merged_outputs),
                "consumes_from": list(branch_result_event_ids),
                "rich": {"json": {"branch_results": list(branch_result_event_ids)}},
            },
        )


class PipelineUiContext:
    """Per-pipeline UI state holder that owns ids and payload assembly."""

    def __init__(
        self,
        session: "WorkflowUiSession",
        pipeline_id: str,
        *,
        last_event_id: Optional[str] = None,
        parallel_group_id: Optional[str] = None,
        branch_id: Optional[str] = None,
        parallel_branch_index: Optional[int] = None,
        parallel_branch_count: Optional[int] = None,
        key_sources: Optional[Dict[str, str]] = None,
    ) -> None:
        self.session = session
        self.pipeline_id = pipeline_id
        self.last_event_id = last_event_id
        self.parallel_group_id = parallel_group_id
        self.branch_id = branch_id
        self.parallel_branch_index = parallel_branch_index
        self.parallel_branch_count = parallel_branch_count
        self.key_sources = key_sources if key_sources is not None else session.key_sources

    @property
    def enabled(self) -> bool:
        return self.session.enabled

    def fork_branch(self, *, branch_id: str, branch_index: int, branch_count: int, last_event_id: str) -> "PipelineUiContext":
        return PipelineUiContext(
            session=self.session,
            pipeline_id=self.pipeline_id,
            last_event_id=last_event_id,
            parallel_group_id=self.parallel_group_id,
            branch_id=branch_id,
            parallel_branch_index=branch_index,
            parallel_branch_count=branch_count,
            key_sources=dict(self.key_sources),
        )

    def workflow_node_kind(self, step_type: str) -> str:
        return self.session.emitter.workflow_node_kind_from_step(step_type)

    def consumes_from(self, input_keys: Sequence[str]) -> List[str]:
        return self.session.emitter.consumes_from_keys(input_keys, self.key_sources)

    def register_outputs(self, outputs: Mapping[str, Any], producer_event_id: str) -> None:
        for key in outputs.keys():
            self.key_sources[str(key)] = producer_event_id

    async def emit_step_start(
        self,
        *,
        step_idx_str: str,
        step_type: str,
        step_name: str,
        input_keys: Sequence[str],
        context: Mapping[str, Any],
        parent_event_id: Optional[str],
    ) -> Dict[str, Any]:
        step_event_prefix = f"{self.pipeline_id}:step:{step_idx_str}"
        start_event_id = f"{step_event_prefix}:start"
        execution_mode = "parallel" if self.branch_id else "serial"
        step_inputs = {k: context.get(k) for k in input_keys} if input_keys else {}
        consumes_from = self.consumes_from(input_keys)
        step_node_kind = self.workflow_node_kind(step_type)
        if self.enabled:
            await self.session.emitter.emit_pipeline_step_start(
                self.session.state,
                event_id=start_event_id,
                parent_event_id=parent_event_id,
                step_node_kind=step_node_kind,
                step_type=step_type,
                execution_mode=execution_mode,
                pipeline_id=self.pipeline_id,
                pipeline_step_id=step_idx_str,
                parallel_group_id=self.parallel_group_id,
                branch_id=self.branch_id,
                parallel_branch_index=self.parallel_branch_index,
                parallel_branch_count=self.parallel_branch_count,
                step_name=step_name,
                step_inputs=step_inputs,
                consumes_from=consumes_from,
            )
        self.last_event_id = start_event_id
        return {
            "step_event_prefix": step_event_prefix,
            "start_event_id": start_event_id,
            "step_inputs": step_inputs,
            "consumes_from": consumes_from,
            "step_node_kind": step_node_kind,
            "execution_mode": execution_mode,
        }

    async def emit_step_skipped(
        self,
        *,
        skip_event_id: str,
        start_event_id: str,
        step_idx_str: str,
        step_type: str,
        step_name: str,
        step_node_kind: str,
        execution_mode: str,
        consumes_from: Sequence[str],
    ) -> None:
        if self.enabled:
            await self.session.emitter.emit_pipeline_step_result(
                self.session.state,
                event_id=skip_event_id,
                parent_event_id=start_event_id,
                step_node_kind=step_node_kind,
                step_type=step_type,
                execution_mode=execution_mode,
                pipeline_id=self.pipeline_id,
                pipeline_step_id=step_idx_str,
                parallel_group_id=self.parallel_group_id,
                branch_id=self.branch_id,
                parallel_branch_index=self.parallel_branch_index,
                parallel_branch_count=self.parallel_branch_count,
                step_name=step_name,
                step_inputs={},
                outputs={},
                consumes_from=consumes_from,
                skipped=True,
            )
        self.last_event_id = skip_event_id

    async def emit_step_result(
        self,
        *,
        result_event_id: str,
        start_event_id: str,
        step_idx_str: str,
        step_type: str,
        step_name: str,
        step_node_kind: str,
        execution_mode: str,
        step_inputs: Mapping[str, Any],
        outputs: Mapping[str, Any],
        consumes_from: Sequence[str],
    ) -> None:
        if self.enabled:
            await self.session.emitter.emit_pipeline_step_result(
                self.session.state,
                event_id=result_event_id,
                parent_event_id=start_event_id,
                step_node_kind=step_node_kind,
                step_type=step_type,
                execution_mode=execution_mode,
                pipeline_id=self.pipeline_id,
                pipeline_step_id=step_idx_str,
                parallel_group_id=self.parallel_group_id,
                branch_id=self.branch_id,
                parallel_branch_index=self.parallel_branch_index,
                parallel_branch_count=self.parallel_branch_count,
                step_name=step_name,
                step_inputs=step_inputs,
                outputs=outputs,
                consumes_from=consumes_from,
            )
        self.last_event_id = result_event_id
        self.register_outputs(outputs, result_event_id)

    async def emit_step_error(
        self,
        *,
        error_event_id: str,
        start_event_id: str,
        step_idx_str: str,
        step_type: str,
        step_name: str,
        step_node_kind: str,
        execution_mode: str,
        step_inputs: Mapping[str, Any],
        error: str,
        consumes_from: Sequence[str],
    ) -> None:
        if self.enabled:
            await self.session.emitter.emit_pipeline_step_error(
                self.session.state,
                event_id=error_event_id,
                parent_event_id=start_event_id,
                step_node_kind=step_node_kind,
                step_type=step_type,
                execution_mode=execution_mode,
                pipeline_id=self.pipeline_id,
                pipeline_step_id=step_idx_str,
                parallel_group_id=self.parallel_group_id,
                branch_id=self.branch_id,
                parallel_branch_index=self.parallel_branch_index,
                parallel_branch_count=self.parallel_branch_count,
                step_name=step_name,
                step_inputs=step_inputs,
                error=error,
                consumes_from=consumes_from,
            )
        self.last_event_id = error_event_id

    async def emit_parallel_group_start(
        self,
        *,
        step_idx_str: str,
        step_name: str,
        input_keys: Sequence[str],
        context: Mapping[str, Any],
        parent_event_id: str,
        branch_count: int,
    ) -> Dict[str, Any]:
        parallel_group_id = f"{self.pipeline_id}:parallel:{step_idx_str}"
        group_start_event_id = f"{parallel_group_id}:start"
        consumes_from = self.consumes_from(input_keys)
        if self.enabled:
            await self.session.emitter.emit_parallel_group_start(
                self.session.state,
                event_id=group_start_event_id,
                parent_event_id=parent_event_id,
                pipeline_id=self.pipeline_id,
                pipeline_step_id=step_idx_str,
                parallel_group_id=parallel_group_id,
                step_name=step_name,
                group_inputs={k: context.get(k) for k in input_keys if k in context},
                consumes_from=consumes_from,
                branch_count=branch_count,
            )
        self.last_event_id = group_start_event_id
        return {"parallel_group_id": parallel_group_id, "group_start_event_id": group_start_event_id, "consumes_from": consumes_from}

    async def emit_parallel_branch_start(
        self,
        *,
        step_idx_str: str,
        sub_idx: int,
        parallel_group_id: str,
        group_start_event_id: str,
        branch_count: int,
    ) -> Dict[str, str]:
        branch_id = f"{parallel_group_id}:branch:{sub_idx}"
        branch_start_event_id = f"{branch_id}:start"
        if self.enabled:
            await self.session.emitter.emit_parallel_branch_start(
                self.session.state,
                event_id=branch_start_event_id,
                parent_event_id=group_start_event_id,
                pipeline_id=self.pipeline_id,
                pipeline_step_id=f"{step_idx_str}.{sub_idx}",
                parallel_group_id=parallel_group_id,
                branch_id=branch_id,
                branch_index=sub_idx,
                branch_count=branch_count,
            )
        return {"branch_id": branch_id, "branch_start_event_id": branch_start_event_id}

    async def emit_parallel_branch_result(
        self,
        *,
        step_idx_str: str,
        idx: int,
        parallel_group_id: str,
        branch_id: str,
        branch_last_event_id: str,
        branch_count: int,
        outputs: Mapping[str, Any],
    ) -> str:
        branch_result_event_id = f"{parallel_group_id}:branch:{idx}:result"
        if self.enabled:
            await self.session.emitter.emit_parallel_branch_result(
                self.session.state,
                event_id=branch_result_event_id,
                parent_event_id=branch_last_event_id,
                pipeline_id=self.pipeline_id,
                pipeline_step_id=f"{step_idx_str}.{idx}",
                parallel_group_id=parallel_group_id,
                branch_id=branch_id,
                branch_index=idx,
                branch_count=branch_count,
                outputs=outputs,
            )
        return branch_result_event_id

    async def emit_parallel_merge(
        self,
        *,
        step_idx_str: str,
        step_name: str,
        parallel_group_id: str,
        group_start_event_id: str,
        merged_outputs: Mapping[str, Any],
        branch_result_event_ids: Sequence[str],
    ) -> str:
        merge_event_id = f"{parallel_group_id}:merge"
        if self.enabled:
            await self.session.emitter.emit_parallel_group_merge(
                self.session.state,
                event_id=merge_event_id,
                parent_event_id=group_start_event_id,
                pipeline_id=self.pipeline_id,
                pipeline_step_id=step_idx_str,
                parallel_group_id=parallel_group_id,
                step_name=step_name,
                merged_outputs=merged_outputs,
                branch_result_event_ids=branch_result_event_ids,
            )
        self.last_event_id = merge_event_id
        return merge_event_id


class WorkflowUiSession:
    """Engine-facing facade. Engine can ignore it when disabled."""

    def __init__(self, state: MutableMapping[str, Any], emitter: Optional[WorkflowUiEmitter] = None) -> None:
        self.state = state
        self.emitter = emitter or WorkflowUiEmitter()
        self.enabled = bool(state and state.get("thread_id"))
        self.key_sources: Dict[str, str] = dict((state or {}).get("ui_key_sources") or {})

    @classmethod
    def from_state(cls, state: Optional[MutableMapping[str, Any]], emitter: Optional[WorkflowUiEmitter] = None) -> Optional["WorkflowUiSession"]:
        if state is None:
            return None
        return cls(state, emitter=emitter)

    def persist(self) -> None:
        if self.state is not None:
            self.state["ui_key_sources"] = dict(self.key_sources)

    async def emit_planner_decision(
        self,
        *,
        chosen: str,
        reason: str,
        available_data_keys: Sequence[str],
        ready_to_run: Sequence[str],
        unblockers: Sequence[str],
    ) -> None:
        if not self.enabled:
            return
        await self.emitter.emit_planner_decision(
            self.state,
            chosen=chosen,
            reason=reason,
            available_data_keys=available_data_keys,
            ready_to_run=ready_to_run,
            unblockers=unblockers,
        )

    async def emit_agent_action(
        self,
        *,
        skill_name: str,
        node_kind: str,
        input_ctx: Mapping[str, Any],
        executor: str,
        required_inputs: Sequence[str],
    ) -> Dict[str, Any]:
        action_event_id = f"{self.state.get('thread_id')}:{skill_name}:action:{datetime.utcnow().timestamp()}"
        consumes_from = self.emitter.consumes_from_keys(list(required_inputs), self.key_sources)
        if self.enabled:
            await self.emitter.emit_agent_action(
                self.state,
                event_id=action_event_id,
                skill_name=skill_name,
                node_kind=node_kind,
                input_ctx=input_ctx,
                consumes_from=consumes_from,
                executor=executor,
                required_inputs=required_inputs,
            )
        return {"action_event_id": action_event_id, "consumes_from": consumes_from}

    async def emit_agent_result(
        self,
        *,
        action_event_id: str,
        skill_name: str,
        node_kind: str,
        input_ctx: Mapping[str, Any],
        outputs: Mapping[str, Any],
        consumes_from: Sequence[str],
    ) -> str:
        result_event_id = f"{self.state.get('thread_id')}:{skill_name}:result:{datetime.utcnow().timestamp()}"
        if self.enabled:
            await self.emitter.emit_agent_result(
                self.state,
                event_id=result_event_id,
                parent_event_id=action_event_id,
                skill_name=skill_name,
                node_kind=node_kind,
                input_ctx=input_ctx,
                outputs=outputs,
                consumes_from=consumes_from,
            )
        for path in outputs.keys():
            self.key_sources[path] = result_event_id
        return result_event_id

    async def emit_agent_error(
        self,
        *,
        action_event_id: str,
        skill_name: str,
        node_kind: str,
        input_ctx: Mapping[str, Any],
        error_msg: str,
        consumes_from: Sequence[str],
    ) -> None:
        if not self.enabled:
            return
        await self.emitter.emit_agent_error(
            self.state,
            parent_event_id=action_event_id,
            skill_name=skill_name,
            node_kind=node_kind,
            input_ctx=input_ctx,
            error_msg=error_msg,
            consumes_from=consumes_from,
        )

    async def begin_pipeline(self, *, step_count: int, inputs: Mapping[str, Any]) -> PipelineUiContext:
        pipeline_id = f"pipeline:{datetime.utcnow().timestamp()}"
        ctx = PipelineUiContext(self, pipeline_id=pipeline_id)
        if self.enabled:
            await self.emitter.emit_pipeline_start(
                self.state,
                pipeline_id=pipeline_id,
                step_count=step_count,
                inputs=inputs,
            )
        ctx.last_event_id = f"{pipeline_id}:start"
        return ctx

    async def complete_pipeline(self, ctx: PipelineUiContext, *, inputs: Mapping[str, Any], outputs: Mapping[str, Any]) -> None:
        if self.enabled:
            await self.emitter.emit_pipeline_complete(
                self.state,
                pipeline_id=ctx.pipeline_id,
                parent_event_id=ctx.last_event_id,
                inputs=inputs,
                outputs=outputs,
                output_keys=list(outputs.keys()),
            )
        self.key_sources = dict(ctx.key_sources)
        self.persist()
