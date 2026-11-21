"use client";

import { pct, type GraphEdge } from "@/components/graph/graph-view";

const SIGNALS: { key: "answers" | "reactions" | "roots" | "social"; label: string }[] = [
  { key: "answers", label: "Answers" },
  { key: "reactions", label: "Reactions" },
  { key: "roots", label: "Roots" },
  { key: "social", label: "Likes & follows" },
];

/** One pair's score and why (tasks 5.6, 7.3). Roots only ever say "Shared roots". */
export function EdgeDetails({
  edge,
  names,
  onClose,
}: {
  edge: GraphEdge;
  names: Record<string, string>;
  onClose?: () => void;
}) {
  return (
    <div className="sticker bg-surface animate-pop space-y-3 p-4">
      <div className="flex items-start justify-between gap-3">
        <p className="font-heading font-extrabold">
          {names[edge.a] ?? "?"} &amp; {names[edge.b] ?? "?"}
        </p>
        <span className="bg-highlight border-ink font-display rounded-[6px] border-2 px-2 text-2xl tabular-nums">
          {pct(edge.total)}
        </span>
      </div>
      {edge.reasons.length > 0 && (
        <ul className="space-y-1 text-sm">
          {edge.reasons.map((r) => (
            <li key={r.text}>• {r.text}</li>
          ))}
        </ul>
      )}
      <dl className="text-foreground/70 grid grid-cols-2 gap-x-4 gap-y-1 text-xs">
        {SIGNALS.map((s) => (
          <div key={s.key} className="flex justify-between">
            <dt>{s.label}</dt>
            <dd className="tabular-nums">
              {edge[s.key] == null ? "not enough data" : pct(edge[s.key]!)}
            </dd>
          </div>
        ))}
      </dl>
      {onClose && (
        <button onClick={onClose} className="text-foreground/75 text-sm font-semibold underline">
          Close
        </button>
      )}
    </div>
  );
}
