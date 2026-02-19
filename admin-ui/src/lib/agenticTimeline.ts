import type { RunEvent } from "./types";

export type WorkflowPhase =
  | "planner_decision"
  | "agent_action"
  | "agent_result"
  | "agent_error"
  | "pipeline_step_start"
  | "pipeline_step_result"
  | "pipeline_step_error"
  | "parallel_group_start"
  | "parallel_branch_start"
  | "parallel_branch_result"
  | "parallel_group_merge"
  | "workflow_update";

export interface TimelineRichPayload {
  images: string[];
  urls: string[];
  json: unknown | null;
  wkt: string[];
}

export interface TimelineEvent {
  eventId: string;
  parentEventId: string | null;
  threadId: string;
  timestamp: string;
  phase: WorkflowPhase;
  category: "decision" | "action" | "result" | "error" | "fact";
  agentName: string;
  message: string;
  reasoning?: string;
  nodeKind?: string;
  stepType?: string;
  executionMode?: "serial" | "parallel" | "parallel_group";
  pipelineId?: string | null;
  pipelineStepId?: string | null;
  parallelGroupId?: string | null;
  branchId?: string | null;
  parallelBranchIndex?: number | null;
  parallelBranchCount?: number | null;
  consumesFrom: string[];
  inputs: Record<string, unknown>;
  outputs: Record<string, unknown>;
  rich: TimelineRichPayload;
  raw: RunEvent;
}

const URL_REGEX = /(https?:\/\/[^\s<>"'`]+)/gi;
const WKT_TYPE_REGEX =
  /\b(POINT|LINESTRING|POLYGON|MULTIPOINT|MULTILINESTRING|MULTIPOLYGON)\s*\(/gi;

function safeObject(value: unknown): Record<string, unknown> {
  return value && typeof value === "object" && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : {};
}

function stringifyUnknown(value: unknown): string {
  if (typeof value === "string") return value;
  if (typeof value === "number" || typeof value === "boolean") return String(value);
  if (value && typeof value === "object") return JSON.stringify(value);
  return "";
}

function numberOrNull(value: unknown): number | null {
  if (typeof value === "number" && Number.isFinite(value)) return value;
  if (typeof value === "string" && value.trim()) {
    const parsed = Number(value);
    if (Number.isFinite(parsed)) return parsed;
  }
  return null;
}

function collectStrings(value: unknown, out: string[] = []): string[] {
  if (typeof value === "string") {
    out.push(value);
    return out;
  }
  if (Array.isArray(value)) {
    value.forEach((item) => collectStrings(item, out));
    return out;
  }
  if (value && typeof value === "object") {
    Object.values(value as Record<string, unknown>).forEach((v) => collectStrings(v, out));
  }
  return out;
}

function extractUrls(text: string): string[] {
  const matches = text.match(URL_REGEX) || [];
  return Array.from(new Set(matches.map((url) => url.replace(/[),.;]+$/, ""))));
}

function isImageUrl(url: string): boolean {
  return /\.(png|jpe?g|gif|webp|svg)(\?.*)?$/i.test(url);
}

function extractWkt(text: string): string[] {
  const values: string[] = [];
  let match: RegExpExecArray | null;

  while ((match = WKT_TYPE_REGEX.exec(text))) {
    const start = match.index;
    const openParenIndex = text.indexOf("(", start);
    if (openParenIndex === -1) continue;

    let depth = 0;
    let end = -1;
    for (let i = openParenIndex; i < text.length; i += 1) {
      const ch = text[i];
      if (ch === "(") depth += 1;
      if (ch === ")") depth -= 1;
      if (depth === 0) {
        end = i;
        break;
      }
    }

    if (end > openParenIndex) {
      values.push(text.slice(start, end + 1).trim());
    }
  }

  return Array.from(new Set(values));
}

function detectPhase(value: unknown): WorkflowPhase {
  const phase = String(value || "").toLowerCase();
  if (phase === "planner_decision") return phase;
  if (phase === "agent_action") return phase;
  if (phase === "agent_result") return phase;
  if (phase === "agent_error") return phase;
  if (phase === "pipeline_step_start") return phase;
  if (phase === "pipeline_step_result") return phase;
  if (phase === "pipeline_step_error") return phase;
  if (phase === "parallel_group_start") return phase;
  if (phase === "parallel_branch_start") return phase;
  if (phase === "parallel_branch_result") return phase;
  if (phase === "parallel_group_merge") return phase;
  return "workflow_update";
}

function categoryFromPhase(phase: WorkflowPhase): TimelineEvent["category"] {
  if (phase === "planner_decision") return "decision";
  if (phase === "agent_action" || phase === "pipeline_step_start" || phase === "parallel_group_start" || phase === "parallel_branch_start") return "action";
  if (phase === "agent_result") return "result";
  if (phase === "pipeline_step_result" || phase === "parallel_branch_result" || phase === "parallel_group_merge") return "result";
  if (phase === "agent_error" || phase === "pipeline_step_error") return "error";
  return "fact";
}

export function normalizeWorkflowUiEvent(event: RunEvent): TimelineEvent | null {
  const eventType = event?.type || event?.event;
  if (eventType !== "workflow_ui_update") return null;

  const envelope = safeObject(event);
  const richObject = safeObject(envelope.rich);
  const inputs = safeObject(envelope.inputs);
  const outputs = safeObject(envelope.outputs);
  const payload = safeObject(envelope.payload);

  const message =
    stringifyUnknown(envelope.message) ||
    stringifyUnknown(payload.message) ||
    stringifyUnknown(envelope.text) ||
    "Workflow update";

  const phase = detectPhase(envelope.phase || payload.phase);
  const threadId = stringifyUnknown(envelope.thread_id) || "unknown";
  const timestamp = stringifyUnknown(envelope.timestamp) || new Date().toISOString();
  const agentName =
    stringifyUnknown(envelope.agent_name) ||
    stringifyUnknown(envelope.source) ||
    stringifyUnknown(payload.agent_name) ||
    (phase === "planner_decision" ? "planner" : "agent");

  const richJson = richObject.json ?? (Object.keys(payload).length > 0 ? payload : null);
  const richStrings = [message, ...collectStrings(richJson)];
  const richUrls = Array.from(
    new Set([
      ...richStrings.flatMap((text) => extractUrls(text)),
      ...(Array.isArray(richObject.urls) ? richObject.urls.map((v) => stringifyUnknown(v)) : []),
    ])
  ).filter(Boolean);

  const images = Array.from(
    new Set([
      ...richUrls.filter(isImageUrl),
      ...(Array.isArray(richObject.images) ? richObject.images.map((v) => stringifyUnknown(v)) : []),
    ])
  ).filter(Boolean);

  const wkt = Array.from(
    new Set([
      ...richStrings.flatMap((text) => extractWkt(text)),
      ...(Array.isArray(richObject.wkt) ? richObject.wkt.map((v) => stringifyUnknown(v)) : []),
    ])
  ).filter(Boolean);

  const consumesFrom = Array.isArray(envelope.consumes_from)
    ? envelope.consumes_from.map((v) => stringifyUnknown(v)).filter(Boolean)
    : [];

  return {
    eventId:
      stringifyUnknown(envelope.event_id) ||
      `${threadId}:${phase}:${new Date(timestamp).getTime()}:${Math.random().toString(36).slice(2, 8)}`,
    parentEventId: stringifyUnknown(envelope.parent_event_id) || null,
    threadId,
    timestamp,
    phase,
    category: categoryFromPhase(phase),
    agentName,
    message,
    reasoning: stringifyUnknown(envelope.reasoning) || stringifyUnknown(payload.reasoning) || undefined,
    nodeKind: stringifyUnknown(envelope.node_kind) || undefined,
    stepType: stringifyUnknown(envelope.step_type) || undefined,
    executionMode:
      ((): "serial" | "parallel" | "parallel_group" | undefined => {
        const mode = stringifyUnknown(envelope.execution_mode).toLowerCase();
        if (mode === "serial" || mode === "parallel" || mode === "parallel_group") return mode;
        return undefined;
      })(),
    pipelineId: stringifyUnknown(envelope.pipeline_id) || null,
    pipelineStepId: stringifyUnknown(envelope.pipeline_step_id) || null,
    parallelGroupId: stringifyUnknown(envelope.parallel_group_id) || null,
    branchId: stringifyUnknown(envelope.branch_id) || null,
    parallelBranchIndex: numberOrNull(envelope.parallel_branch_index),
    parallelBranchCount: numberOrNull(envelope.parallel_branch_count),
    consumesFrom,
    inputs,
    outputs,
    rich: {
      images,
      urls: richUrls,
      json: richJson,
      wkt,
    },
    raw: event,
  };
}
