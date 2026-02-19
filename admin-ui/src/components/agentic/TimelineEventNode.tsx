"use client";

import { Handle, Position, type NodeProps } from "reactflow";
import type { TimelineNodeData } from "../../lib/agenticGraph";

interface ParsedGeometry {
  type: "POINT" | "LINESTRING" | "POLYGON" | "MULTIPOINT" | "MULTILINESTRING" | "MULTIPOLYGON";
  points: Array<[number, number]>;
}

function truncate(text: string, limit = 120): string {
  if (text.length <= limit) return text;
  return `${text.slice(0, limit - 3)}...`;
}

function parseCoordinatePair(value: string): [number, number] | null {
  const parts = value.trim().split(/\s+/);
  if (parts.length < 2) return null;
  const x = Number(parts[0]);
  const y = Number(parts[1]);
  if (!Number.isFinite(x) || !Number.isFinite(y)) return null;
  return [x, y];
}

function parseCoordinateList(value: string): Array<[number, number]> {
  return value
    .split(",")
    .map((pair) => parseCoordinatePair(pair))
    .filter((coord): coord is [number, number] => coord !== null);
}

function parseWktGeometry(wkt: string): ParsedGeometry | null {
  const cleaned = wkt.replace(/^SRID=\d+;/i, "").trim();
  const match = cleaned.match(/^([A-Z]+)\s*\(([\s\S]+)\)$/i);
  if (!match) return null;

  const type = match[1].toUpperCase();
  const body = match[2].trim();
  if (type === "POINT") {
    const point = parseCoordinatePair(body);
    return point ? { type: "POINT", points: [point] } : null;
  }
  if (type === "LINESTRING") {
    const points = parseCoordinateList(body);
    return points.length > 1 ? { type: "LINESTRING", points } : null;
  }
  if (type === "POLYGON") {
    const firstRingMatch = body.match(/^\(([^)]+)\)/);
    const ring = firstRingMatch ? firstRingMatch[1] : body;
    const points = parseCoordinateList(ring);
    return points.length > 2 ? { type: "POLYGON", points } : null;
  }
  if (type === "MULTIPOINT") {
    const normalized = body.replace(/\(/g, "").replace(/\)/g, "");
    const points = parseCoordinateList(normalized);
    return points.length > 0 ? { type: "MULTIPOINT", points } : null;
  }
  if (type === "MULTILINESTRING") {
    const segments = body.match(/\(([^()]+)\)/g) || [];
    const points = segments.flatMap((seg) => parseCoordinateList(seg.replace(/[()]/g, "")));
    return points.length > 1 ? { type: "MULTILINESTRING", points } : null;
  }
  if (type === "MULTIPOLYGON") {
    // Extract all coordinate pairs from all polygon rings and flatten for preview bounds/drawing.
    const numericPairs = body.match(/-?\d+(?:\.\d+)?\s+-?\d+(?:\.\d+)?/g) || [];
    const points = numericPairs
      .map((pair) => parseCoordinatePair(pair))
      .filter((coord): coord is [number, number] => coord !== null);
    return points.length > 2 ? { type: "MULTIPOLYGON", points } : null;
  }
  return null;
}

function WktMapPreview({ wkt }: { wkt: string }) {
  const geometry = parseWktGeometry(wkt);
  if (!geometry) {
    return (
      <div className="rounded border border-slate-300 bg-slate-50 p-1.5 text-[10px] text-slate-600">
        {truncate(wkt, 80)}
      </div>
    );
  }

  const xs = geometry.points.map(([x]) => x);
  const ys = geometry.points.map(([, y]) => y);
  const minX = Math.min(...xs);
  const maxX = Math.max(...xs);
  const minY = Math.min(...ys);
  const maxY = Math.max(...ys);
  const width = 130;
  const height = 88;
  const pad = 8;
  const rangeX = maxX - minX || 1;
  const rangeY = maxY - minY || 1;

  const pointPairs = geometry.points
    .map(([x, y]) => {
      const px = pad + ((x - minX) / rangeX) * (width - pad * 2);
      const py = height - pad - ((y - minY) / rangeY) * (height - pad * 2);
      return `${px},${py}`;
    });
  const points = pointPairs.join(" ");

  return (
    <div className="rounded border border-slate-300 bg-slate-50 p-1">
      <svg width={width} height={height} className="rounded bg-white border border-slate-200">
        {Array.from({ length: 5 }).map((_, idx) => (
          <line
            // eslint-disable-next-line react/no-array-index-key
            key={`grid-x-${idx}`}
            x1={(idx + 1) * (width / 6)}
            y1={0}
            x2={(idx + 1) * (width / 6)}
            y2={height}
            stroke="#e2e8f0"
            strokeWidth={0.6}
          />
        ))}
        {Array.from({ length: 3 }).map((_, idx) => (
          <line
            // eslint-disable-next-line react/no-array-index-key
            key={`grid-y-${idx}`}
            x1={0}
            y1={(idx + 1) * (height / 4)}
            x2={width}
            y2={(idx + 1) * (height / 4)}
            stroke="#e2e8f0"
            strokeWidth={0.6}
          />
        ))}
        {geometry.type === "POINT" && (
          <circle cx={points.split(",")[0]} cy={points.split(",")[1]} r={4.5} fill="#2563eb" />
        )}
        {geometry.type === "LINESTRING" && (
          <polyline points={points} fill="none" stroke="#2563eb" strokeWidth={2.2} />
        )}
        {geometry.type === "MULTILINESTRING" && (
          <polyline points={points} fill="none" stroke="#2563eb" strokeWidth={2.2} />
        )}
        {geometry.type === "POLYGON" && (
          <polygon points={points} fill="rgba(37,99,235,0.20)" stroke="#2563eb" strokeWidth={2} />
        )}
        {geometry.type === "MULTIPOLYGON" && (
          <polygon points={points} fill="rgba(37,99,235,0.20)" stroke="#2563eb" strokeWidth={2} />
        )}
        {geometry.type === "MULTIPOINT" && (
          <>
            {geometry.points.map((_, idx) => {
              const [px, py] = pointPairs[idx]?.split(",") || [];
              return (
                <circle
                  // eslint-disable-next-line react/no-array-index-key
                  key={`point-${idx}`}
                  cx={px}
                  cy={py}
                  r={3.2}
                  fill="#2563eb"
                />
              );
            })}
          </>
        )}
      </svg>
    </div>
  );
}

function badgeClass(category: TimelineNodeData["event"]["category"]): string {
  if (category === "decision") return "bg-purple-100 text-purple-700 border-purple-200";
  if (category === "action") return "bg-amber-100 text-amber-700 border-amber-200";
  if (category === "result") return "bg-emerald-100 text-emerald-700 border-emerald-200";
  if (category === "error") return "bg-red-100 text-red-700 border-red-200";
  return "bg-slate-100 text-slate-700 border-slate-200";
}

function kindClass(kind?: string): string {
  const normalized = String(kind || "").toLowerCase();
  if (normalized === "llm") return "bg-fuchsia-50 text-fuchsia-700 border-fuchsia-200";
  if (normalized === "data_query") return "bg-cyan-50 text-cyan-700 border-cyan-200";
  if (normalized === "rest") return "bg-teal-50 text-teal-700 border-teal-200";
  if (normalized === "function") return "bg-indigo-50 text-indigo-700 border-indigo-200";
  if (normalized === "pipeline") return "bg-amber-50 text-amber-700 border-amber-200";
  if (normalized === "merge") return "bg-emerald-50 text-emerald-700 border-emerald-200";
  if (normalized === "conditional") return "bg-violet-50 text-violet-700 border-violet-200";
  return "bg-slate-50 text-slate-700 border-slate-200";
}

export default function TimelineEventNode({ data }: NodeProps<TimelineNodeData>) {
  const { event, isLatest } = data;
  const hasWkt = event.rich.wkt.length > 0;
  const hasImage = event.rich.images.length > 0;

  return (
    <div
      className={`w-[280px] rounded-xl border bg-white shadow-sm ${
        isLatest ? "border-blue-300 ring-2 ring-blue-200/60" : "border-slate-200"
      }`}
    >
      <Handle type="target" position={Position.Left} className="!w-2 !h-2 !bg-slate-300" />
      <div className="px-3 py-2 border-b border-slate-100">
        <div className="flex items-center justify-between gap-2">
          <span className={`text-[10px] px-1.5 py-0.5 rounded border uppercase ${badgeClass(event.category)}`}>
            {event.phase.replace("_", " ")}
          </span>
          <span className="text-[10px] text-slate-500">{new Date(event.timestamp).toLocaleTimeString()}</span>
        </div>
        <div className="mt-1 flex items-center gap-1.5 flex-wrap">
          <p className="text-xs font-semibold text-slate-900">{event.agentName}</p>
          {event.nodeKind && (
            <span className={`text-[10px] px-1.5 py-0.5 rounded border ${kindClass(event.nodeKind)}`}>
              {event.nodeKind}
            </span>
          )}
        </div>
      </div>
      <div className="p-3 space-y-2">
        <p className="text-xs text-slate-800 leading-5">{truncate(event.message, 145)}</p>
        {event.reasoning && (
          <p className="text-[11px] text-slate-600 bg-slate-50 border border-slate-200 rounded p-1.5">
            {truncate(event.reasoning, 140)}
          </p>
        )}
        {hasImage && (
          <img
            src={event.rich.images[0]}
            alt="event-preview"
            className="w-full h-24 object-cover rounded border border-slate-200"
          />
        )}
        {hasWkt && <WktMapPreview wkt={event.rich.wkt[0]} />}
      </div>
      <Handle type="source" position={Position.Right} className="!w-2 !h-2 !bg-slate-400" />
    </div>
  );
}
