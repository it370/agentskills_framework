"use client";

import type { NodeProps } from "reactflow";
import type { TimelineNodeData } from "../../lib/agenticGraph";
import TimelineEventNode from "./TimelineEventNode";

export default function LlmNode(props: NodeProps<TimelineNodeData>) {
  return <TimelineEventNode {...props} />;
}
