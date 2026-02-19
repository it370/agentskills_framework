"use client";

import type { NodeProps } from "reactflow";
import type { TimelineNodeData } from "../../lib/agenticGraph";
import { Handle, Position } from "reactflow";
import TimelineEventNode from "./TimelineEventNode";

function stepIcon(stepType: string, nodeKind: string): string {
  const normalized = String(stepType || "").toLowerCase();
  if (normalized === "skill") return "[SK]";
  if (normalized === "transform") return "[FX]";
  if (normalized === "merge" || normalized === "parallel_merge") return "[MG]";
  if (normalized === "rest") return "[API]";
  if (normalized === "query") return "[QRY]";
  if (normalized === "parallel") return "[PAR]";
  if (normalized === "parallel_branch") return "[BR]";
  if (normalized === "conditional") return "[IF]";
  if (normalized === "pipeline") return "[PIPE]";
  const byKind = String(nodeKind || "").toLowerCase();
  if (byKind === "llm") return "[LLM]";
  if (byKind === "data_query") return "[QRY]";
  if (byKind === "rest") return "[API]";
  if (byKind === "function") return "[FX]";
  if (byKind === "merge") return "[MG]";
  return "[STEP]";
}

export default function PipelineStepNode(props: NodeProps<TimelineNodeData>) {
  const { data } = props;
  const rows = data.pipelineRows || [];

  if (rows.length === 0) {
    return <TimelineEventNode {...props} />;
  }

  return (
    <div className="w-[560px] rounded-xl border border-amber-300 bg-amber-50/50 shadow-sm">
      <Handle type="target" position={Position.Left} className="!w-2 !h-2 !bg-amber-400" />
      <div className="px-3 py-2 border-b border-amber-200 bg-amber-100/60">
        <p className="text-xs font-semibold text-amber-900">{data.event.message}</p>
        <p className="text-[11px] text-amber-700">
          Pipeline steps: {rows.length} | {new Date(data.event.timestamp).toLocaleTimeString()}
        </p>
      </div>
      <div className="p-3 space-y-2 bg-white/70">
        {rows.map((row, index) => (
          <div key={row.id} className="relative">
            {index > 0 && (
              <div className="absolute -top-2 left-1/2 -translate-x-1/2 flex items-center gap-1">
                <span className="w-1.5 h-1.5 rounded-full bg-amber-400" />
                <span className="w-1.5 h-1.5 rounded-full bg-amber-400" />
                <span className="w-1.5 h-1.5 rounded-full bg-amber-400" />
              </div>
            )}
            <div className="grid grid-cols-2 gap-2 rounded-lg border border-amber-200 bg-white p-2">
              <div className="rounded border border-slate-200 bg-slate-50 p-2">
                <div className="flex items-center justify-between gap-2">
                  <p className="text-[11px] font-semibold text-slate-800">
                    {stepIcon(row.stepType, row.nodeKind)} Step {index + 1}: {row.stepLabel}
                  </p>
                  {row.executionMode === "parallel" && (
                    <span className="text-[10px] px-1.5 py-0.5 rounded border border-violet-200 bg-violet-50 text-violet-700">
                      parallel
                    </span>
                  )}
                </div>
                <p className="text-[10px] text-slate-600 mt-0.5">Type: {row.nodeKind}</p>
                <p className="text-[11px] text-slate-700 mt-1">{row.detailMessage}</p>
                <pre className="text-[10px] text-slate-700 mt-1 bg-white border border-slate-200 rounded p-1 overflow-auto max-h-20">
                  {JSON.stringify(row.detailInputs, null, 2)}
                </pre>
              </div>
              <div className="rounded border border-slate-200 bg-slate-50 p-2">
                <p className="text-[11px] font-semibold text-slate-800">Step Output</p>
                <p className="text-[10px] text-slate-600 mt-0.5">Status: {row.status}</p>
                <pre className="text-[10px] text-slate-700 mt-1 bg-white border border-slate-200 rounded p-1 overflow-auto max-h-28">
                  {JSON.stringify(row.outputData, null, 2)}
                </pre>
              </div>
            </div>
          </div>
        ))}
      </div>
      <div className="px-3 pb-3">
        <div className="rounded border border-emerald-200 bg-emerald-50 p-2">
          <p className="text-[11px] font-semibold text-emerald-800">Pipeline final output</p>
          <pre className="text-[10px] text-emerald-900 mt-1 bg-white border border-emerald-200 rounded p-1 overflow-auto max-h-28">
            {JSON.stringify(data.pipelineOutput || {}, null, 2)}
          </pre>
        </div>
      </div>
      <Handle type="source" position={Position.Right} className="!w-2 !h-2 !bg-amber-500" />
    </div>
  );
}
