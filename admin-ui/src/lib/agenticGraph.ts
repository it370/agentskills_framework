import type { Edge, Node } from "reactflow";
import { MarkerType } from "reactflow";
import type { TimelineEvent } from "./agenticTimeline";

export interface PipelineStepRow {
  id: string;
  stepLabel: string;
  stepType: string;
  nodeKind: string;
  executionMode: "serial" | "parallel" | "parallel_group";
  status: "running" | "completed" | "error";
  detailMessage: string;
  detailInputs: Record<string, unknown>;
  outputData: Record<string, unknown>;
}

export interface TimelineNodeData {
  event: TimelineEvent;
  isLatest: boolean;
  pipelineRows?: PipelineStepRow[];
  pipelineOutput?: Record<string, unknown>;
}

export interface TimelineGraph {
  nodes: Array<Node<TimelineNodeData>>;
  edges: Edge[];
}

export function buildTimelineGraph(events: TimelineEvent[]): TimelineGraph {
  const sortedRaw = [...events].sort(
    (a, b) => new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime()
  );
  const byId = new Map(sortedRaw.map((event) => [event.eventId, event]));

  const groupByPipeline = new Map<string, TimelineEvent[]>();
  sortedRaw.forEach((event) => {
    if (!event.pipelineId) return;
    if (!groupByPipeline.has(event.pipelineId)) groupByPipeline.set(event.pipelineId, []);
    groupByPipeline.get(event.pipelineId)?.push(event);
  });

  const eventToDisplayId = new Map<string, string>();
  const aggregateByPipeline = new Map<
    string,
    { anchorEventId: string; aggregateEvent: TimelineEvent; pipelineRows: PipelineStepRow[]; groupIds: Set<string> }
  >();

  groupByPipeline.forEach((group, pipelineId) => {
    const ordered = [...group].sort(
      (a, b) => new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime()
    );
    const groupIds = new Set(ordered.map((event) => event.eventId));
    const anchor =
      ordered.find((event) => event.phase === "pipeline_step_result" && event.pipelineStepId === "root") ||
      ordered[ordered.length - 1];

    const rowMap = new Map<
      string,
      { start?: TimelineEvent; result?: TimelineEvent; order: number }
    >();
    let rowOrder = 0;
    ordered.forEach((event) => {
      const isRoot = event.pipelineStepId === "root";
      if (isRoot) return;
      const mode = event.executionMode || "serial";
      const branchKey = mode === "parallel" ? (event.branchId || "branch") : "serial";
      const key = `${event.pipelineStepId || "step"}::${branchKey}`;
      if (!rowMap.has(key)) {
        rowMap.set(key, { order: rowOrder });
        rowOrder += 1;
      }
      const row = rowMap.get(key)!;
      if (
        event.phase === "pipeline_step_start" ||
        event.phase === "parallel_group_start" ||
        event.phase === "parallel_branch_start"
      ) {
        row.start = event;
      }
      if (
        event.phase === "pipeline_step_result" ||
        event.phase === "pipeline_step_error" ||
        event.phase === "parallel_branch_result" ||
        event.phase === "parallel_group_merge"
      ) {
        row.result = event;
      }
    });

    const pipelineRows: PipelineStepRow[] = Array.from(rowMap.entries())
      .sort((a, b) => a[1].order - b[1].order)
      .map(([key, value], index) => {
        const source = value.start || value.result;
        const result = value.result || value.start;
        const stepBase = source?.pipelineStepId || key.split("::")[0] || `step_${index + 1}`;
        const explicitParallel = source?.executionMode === "parallel";
        const branchIndex = (source?.parallelBranchIndex ?? index) + 1;
        const label = explicitParallel ? `${stepBase} (branch ${branchIndex})` : stepBase;
        return {
          id: key,
          stepLabel: label,
          stepType: source?.stepType || "step",
          nodeKind: source?.nodeKind || "pipeline",
          executionMode: source?.executionMode || "serial",
          status: result?.phase === "pipeline_step_error" ? "error" : value.result ? "completed" : "running",
          detailMessage: source?.message || "Step update",
          detailInputs: source?.inputs || {},
          outputData: result?.outputs || {},
        };
      });

    const upstreamParent =
      ordered.find(
        (event) =>
          event.parentEventId &&
          !groupIds.has(event.parentEventId) &&
          byId.has(event.parentEventId)
      )?.parentEventId || null;

    const aggregateEvent: TimelineEvent = {
      ...anchor,
      eventId: `pipeline:${pipelineId}:aggregate`,
      parentEventId: upstreamParent,
      phase: "pipeline_step_result",
      category: "result",
      nodeKind: "pipeline",
      message: `Pipeline (${pipelineRows.length} steps)`,
      outputs: anchor.outputs || {},
      consumesFrom: (anchor.consumesFrom || []).filter((producer) => !groupIds.has(producer)),
    };

    ordered.forEach((event) => eventToDisplayId.set(event.eventId, aggregateEvent.eventId));
    aggregateByPipeline.set(pipelineId, {
      anchorEventId: anchor.eventId,
      aggregateEvent,
      pipelineRows,
      groupIds,
    });
  });

  const displayEvents: TimelineEvent[] = [];
  const pipelineRowsByDisplayId = new Map<string, PipelineStepRow[]>();
  sortedRaw.forEach((event) => {
    if (!event.pipelineId) {
      displayEvents.push(event);
      eventToDisplayId.set(event.eventId, event.eventId);
      return;
    }
    const aggregate = aggregateByPipeline.get(event.pipelineId);
    if (!aggregate) return;
    if (event.eventId === aggregate.anchorEventId) {
      displayEvents.push(aggregate.aggregateEvent);
      pipelineRowsByDisplayId.set(aggregate.aggregateEvent.eventId, aggregate.pipelineRows);
    }
  });

  const latestId = displayEvents.length > 0 ? displayEvents[displayEvents.length - 1].eventId : null;
  const nodeIndex = new Map<string, number>();
  displayEvents.forEach((event, idx) => nodeIndex.set(event.eventId, idx));

  const toNodeType = (event: TimelineEvent): string => {
    if (event.nodeKind === "pipeline") return "pipelineStepNode";
    const kind = (event.nodeKind || "").toLowerCase();
    if (kind === "llm") return "llmNode";
    if (kind === "data_query") return "dataQueryNode";
    if (kind === "function") return "functionNode";
    if (kind === "rest") return "restNode";
    if (kind === "merge") return "mergeNode";
    if (event.parallelGroupId && event.branchId) return "parallelBranchNode";
    return "timelineEvent";
  };

  const nodeWidthForEvent = (event: TimelineEvent): number => {
    if (event.nodeKind === "pipeline") return 560;
    return 280;
  };

  const xByDisplayEvent = new Map<string, number>();
  let cursorX = 80;
  const horizontalGap = 120;
  displayEvents.forEach((event) => {
    xByDisplayEvent.set(event.eventId, cursorX);
    cursorX += nodeWidthForEvent(event) + horizontalGap;
  });

  const nodes: Array<Node<TimelineNodeData>> = displayEvents.map((event, index) => {
    return {
      id: event.eventId,
      type: toNodeType(event),
      position: {
        x: xByDisplayEvent.get(event.eventId) || (80 + index * 360),
        y: 120,
      },
      data: {
        event,
        isLatest: latestId === event.eventId,
        pipelineRows: pipelineRowsByDisplayId.get(event.eventId),
        pipelineOutput: event.nodeKind === "pipeline" ? event.outputs : undefined,
      },
      draggable: false,
    };
  });

  const nodeIdSet = new Set(nodes.map((node) => node.id));
  const edges: Edge[] = [];

  const edgeIds = new Set<string>();

  displayEvents.forEach((event, index) => {
    const fallbackParent = index > 0 ? displayEvents[index - 1].eventId : null;
    const fallbackParentEvent = index > 0 ? displayEvents[index - 1] : null;
    const parentMapped = event.parentEventId ? eventToDisplayId.get(event.parentEventId) || event.parentEventId : null;
    let source = parentMapped && nodeIdSet.has(parentMapped) ? parentMapped : fallbackParent;
    // If pipeline was rendered immediately before an agent result/error, chain from pipeline
    // to avoid visual double-branching from the same action node.
    if (
      fallbackParent &&
      fallbackParentEvent?.nodeKind === "pipeline" &&
      (event.phase === "agent_result" || event.phase === "agent_error")
    ) {
      source = fallbackParent;
    }
    if (!source) return;
    if (source === event.eventId) return;
    const edgeId = `execution:${source}->${event.eventId}`;
    if (edgeIds.has(edgeId)) return;
    edgeIds.add(edgeId);

    edges.push({
      id: edgeId,
      source,
      target: event.eventId,
      animated: latestId === event.eventId,
      markerEnd: { type: MarkerType.ArrowClosed },
      style: { strokeWidth: 1.8 },
      data: { kind: "execution" },
    });
  });

  displayEvents.forEach((event) => {
    if (event.nodeKind === "pipeline") return;
    if (!event.consumesFrom || event.consumesFrom.length === 0) return;
    event.consumesFrom.forEach((producerId) => {
      const mappedProducer = eventToDisplayId.get(producerId) || producerId;
      if (!nodeIdSet.has(mappedProducer) || !nodeIdSet.has(event.eventId)) return;
      if (mappedProducer === event.eventId) return;
      const producerIdx = nodeIndex.get(mappedProducer);
      const currentIdx = nodeIndex.get(event.eventId);
      if (producerIdx === undefined || currentIdx === undefined || producerIdx > currentIdx) return;
      const edgeId = `consumption:${mappedProducer}->${event.eventId}`;
      if (edgeIds.has(edgeId)) return;
      edgeIds.add(edgeId);
      edges.push({
        id: edgeId,
        source: mappedProducer,
        target: event.eventId,
        markerEnd: { type: MarkerType.ArrowClosed },
        style: { strokeWidth: 1.2, strokeDasharray: "6 4" },
        animated: false,
        data: { kind: "consumption" },
      });
    });
  });

  const pipelineNodeIds = new Set(
    nodes
      .filter((node) => node.data?.event?.nodeKind === "pipeline")
      .map((node) => node.id)
  );

  const inboundChosenForPipeline = new Set<string>();
  const filteredEdges: Edge[] = [];
  edges.forEach((edge) => {
    if (!pipelineNodeIds.has(edge.target)) {
      filteredEdges.push(edge);
      return;
    }
    const isExecution = edge.data?.kind === "execution";
    if (!isExecution) return;
    if (inboundChosenForPipeline.has(edge.target)) return;
    inboundChosenForPipeline.add(edge.target);
    filteredEdges.push(edge);
  });

  return { nodes, edges: filteredEdges };
}
