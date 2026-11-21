"use client";

import { type GraphData, GraphView } from "@/components/graph/graph-view";

export function SnapshotGraph({ graph, me }: { graph: Record<string, unknown>; me: string }) {
  const data = graph as unknown as GraphData;
  return (
    <GraphView
      data={{ nodes: data.nodes ?? [], edges: data.edges ?? [], follows: data.follows ?? [] }}
      me={me}
    />
  );
}
