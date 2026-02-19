"use client";

import { useEffect, useMemo, useState } from "react";
import ReactFlow, {
  Background,
  Controls,
  MiniMap,
  ReactFlowProvider,
  type Edge,
  type Node,
} from "reactflow";
import { connectThreadAdminEvents, fetchThreadWorkflowUiEvents } from "../lib/api";
import { buildTimelineGraph, type TimelineNodeData } from "../lib/agenticGraph";
import {
  normalizeWorkflowUiEvent,
  type TimelineEvent,
} from "../lib/agenticTimeline";
import TimelineEventNode from "./agentic/TimelineEventNode";
import LlmNode from "./agentic/LlmNode";
import DataQueryNode from "./agentic/DataQueryNode";
import FunctionNode from "./agentic/FunctionNode";
import RestNode from "./agentic/RestNode";
import PipelineStepNode from "./agentic/PipelineStepNode";
import ParallelBranchNode from "./agentic/ParallelBranchNode";
import MergeNode from "./agentic/MergeNode";

interface AgenticRunViewProps {
  threadId: string;
}

const nodeTypes = {
  timelineEvent: TimelineEventNode,
  llmNode: LlmNode,
  dataQueryNode: DataQueryNode,
  functionNode: FunctionNode,
  restNode: RestNode,
  pipelineStepNode: PipelineStepNode,
  parallelBranchNode: ParallelBranchNode,
  mergeNode: MergeNode,
};

function AgenticRunViewCanvas({ threadId }: AgenticRunViewProps) {
  const [events, setEvents] = useState<TimelineEvent[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);

  useEffect(() => {
    if (!threadId) return;
    let cancelled = false;
    setEvents([]);
    setSelectedId(null);

    (async () => {
      try {
        const historical = await fetchThreadWorkflowUiEvents(threadId, 2000);
        if (cancelled) return;
        const normalized = historical
          .map((event) => normalizeWorkflowUiEvent(event))
          .filter((event): event is TimelineEvent => Boolean(event && event.threadId === threadId));
        setEvents((prev) => {
          const seen = new Set(prev.map((item) => item.eventId));
          const merged = [...prev];
          normalized.forEach((item) => {
            if (!seen.has(item.eventId)) {
              seen.add(item.eventId);
              merged.push(item);
            }
          });
          return merged.slice(-1200);
        });
        if (normalized.length > 0) {
          setSelectedId(normalized[normalized.length - 1].eventId);
        }
      } catch (error) {
        console.warn("[AgenticRunView] Failed to load persisted workflow UI events", error);
      }
    })();

    const connection = connectThreadAdminEvents(threadId, (event) => {
      const normalized = normalizeWorkflowUiEvent(event);
      if (!normalized || normalized.threadId !== threadId) return;

      setEvents((prev) => {
        const exists = prev.some((item) => item.eventId === normalized.eventId);
        if (exists) return prev;
        return [...prev, normalized].slice(-1200);
      });
      setSelectedId(normalized.eventId);
    });

    return () => {
      cancelled = true;
      connection.disconnect();
    };
  }, [threadId]);

  const graph = useMemo(() => buildTimelineGraph(events), [events]);
  const selectedNode = useMemo(
    () => graph.nodes.find((node) => node.id === selectedId) || graph.nodes[graph.nodes.length - 1] || null,
    [graph.nodes, selectedId]
  );
  const selected = selectedNode?.data?.event || null;

  const metrics = useMemo(() => {
    return events.reduce(
      (acc, event) => {
        acc[event.category] += 1;
        acc.images += event.rich.images.length;
        acc.maps += event.rich.wkt.length;
        return acc;
      },
      { decision: 0, action: 0, result: 0, error: 0, fact: 0, images: 0, maps: 0 }
    );
  }, [events]);

  const nodes = graph.nodes as Array<Node<TimelineNodeData>>;
  const edges = graph.edges as Edge[];

  return (
    <div className="space-y-3">
      <div className="rounded-lg border border-slate-200 bg-white px-4 py-3 flex items-center justify-between">
        <div>
          <h3 className="text-base font-semibold text-slate-900">Agentic Timeline Canvas</h3>
          <p className="text-xs text-slate-500">Thread {threadId} · workflow_ui_update only</p>
        </div>
        <div className="flex items-center gap-2 text-xs text-slate-600">
          <span>Decision {metrics.decision}</span>
          <span>Action {metrics.action}</span>
          <span>Result {metrics.result}</span>
          <span>Error {metrics.error}</span>
        </div>
      </div>
      <div className="rounded-lg border border-slate-200 bg-slate-50 px-4 py-2 text-xs text-slate-600 flex items-center gap-4">
        <span className="inline-flex items-center gap-1"><span className="w-3 h-[2px] bg-slate-500 inline-block" />Execution edge</span>
        <span className="inline-flex items-center gap-1"><span className="w-3 h-[2px] border-t border-dashed border-slate-500 inline-block" />Data-consumption edge</span>
      </div>

      <div className="grid grid-cols-12 gap-3">
        <div className="col-span-12 xl:col-span-8 rounded-lg border border-slate-200 bg-white overflow-hidden">
          <div className="h-[720px]">
            <ReactFlow
              nodes={nodes}
              edges={edges}
              fitView
              minZoom={0.2}
              maxZoom={1.5}
              nodeTypes={nodeTypes}
              onNodeClick={(_, node) => setSelectedId(node.id)}
            >
              <Background gap={20} size={1} />
              <MiniMap pannable zoomable />
              <Controls />
            </ReactFlow>
          </div>
        </div>

        <aside className="col-span-12 xl:col-span-4 rounded-lg border border-slate-200 bg-white p-3 max-h-[720px] overflow-y-auto">
          {!selected ? (
            <div className="text-sm text-slate-500">Waiting for workflow_ui_update events...</div>
          ) : (
            <div className="space-y-3">
              <div className="border-b border-slate-100 pb-2">
                <p className="text-xs text-slate-500 uppercase tracking-wide">{selected.phase}</p>
                <p className="text-sm font-semibold text-slate-900">{selected.agentName}</p>
                {selected.nodeKind && (
                  <p className="text-[11px] text-slate-600 mt-0.5">Type: {selected.nodeKind}</p>
                )}
                <p className="text-xs text-slate-500 mt-0.5">
                  {new Date(selected.timestamp).toLocaleString()}
                </p>
              </div>

              <div>
                <p className="text-xs font-semibold text-slate-700 mb-1">Message</p>
                <p className="text-sm text-slate-800">{selected.message}</p>
              </div>

              {selected.reasoning && (
                <div>
                  <p className="text-xs font-semibold text-slate-700 mb-1">Reasoning</p>
                  <p className="text-xs text-slate-700 bg-slate-50 border border-slate-200 rounded p-2">
                    {selected.reasoning}
                  </p>
                </div>
              )}

              <div>
                <p className="text-xs font-semibold text-slate-700 mb-1">Inputs</p>
                <pre className="text-[11px] text-slate-700 bg-slate-50 border border-slate-200 rounded p-2 overflow-auto">
                  {JSON.stringify(selected.inputs, null, 2)}
                </pre>
              </div>

              <div>
                <p className="text-xs font-semibold text-slate-700 mb-1">Consumes From</p>
                {selected.consumesFrom.length === 0 ? (
                  <p className="text-[11px] text-slate-500">None</p>
                ) : (
                  <ul className="space-y-1">
                    {selected.consumesFrom.map((item) => (
                      <li key={item} className="text-[11px] text-slate-700 bg-slate-50 border border-slate-200 rounded px-2 py-1 break-all">
                        {item}
                      </li>
                    ))}
                  </ul>
                )}
              </div>

              <div>
                <p className="text-xs font-semibold text-slate-700 mb-1">Outputs</p>
                <pre className="text-[11px] text-slate-700 bg-slate-50 border border-slate-200 rounded p-2 overflow-auto">
                  {JSON.stringify(selectedNode?.data?.pipelineOutput ?? selected.outputs, null, 2)}
                </pre>
              </div>

              {selected.rich.images.length > 0 && (
                <div>
                  <p className="text-xs font-semibold text-slate-700 mb-1">Images</p>
                  <div className="space-y-2">
                    {selected.rich.images.map((img) => (
                      <img
                        key={img}
                        src={img}
                        alt="event-image"
                        className="w-full h-28 object-cover rounded border border-slate-200"
                      />
                    ))}
                  </div>
                </div>
              )}

              {selected.rich.json !== null && (
                <div>
                  <p className="text-xs font-semibold text-slate-700 mb-1">JSON payload</p>
                  <pre className="text-[11px] text-slate-700 bg-slate-50 border border-slate-200 rounded p-2 overflow-auto">
                    {JSON.stringify(selected.rich.json, null, 2)}
                  </pre>
                </div>
              )}
            </div>
          )}
        </aside>
      </div>
    </div>
  );
}

export default function AgenticRunView({ threadId }: AgenticRunViewProps) {
  return (
    <ReactFlowProvider>
      <AgenticRunViewCanvas threadId={threadId} />
    </ReactFlowProvider>
  );
}
