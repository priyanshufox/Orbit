import Link from "next/link";
import { Suspense } from "react";

import { Heading, Loading, Screen, Tag } from "@/components/ui";
import { requireStage } from "@/lib/onboarding";

import { SnapshotGraph } from "./snapshot-graph";

export default function HistoryPage() {
  return (
    <Suspense fallback={<Loading />}>
      <History />
    </Suspense>
  );
}

async function History() {
  const { api, me } = await requireStage("ready");
  const { data: snapshots = [] } = await api.GET("/me/snapshots");
  return (
    <Screen>
      <Heading
        title="Your past orbits"
        lead="When a room is deleted after 48 hours, your own part of its graph is kept here."
      />
      {snapshots.length === 0 && (
        <p className="sticker-sm bg-surface text-foreground/75 p-4">
          Nothing yet. Play a round and come back after the room closes.
        </p>
      )}
      <ul className="space-y-6">
        {snapshots.map((s) => (
          <li key={s.id} className="space-y-2">
            <p className="flex items-center gap-2 text-sm">
              <Tag>Room {s.room_code}</Tag>
              {new Date(s.taken_at).toLocaleDateString(undefined, { dateStyle: "medium" })}
            </p>
            <div className="sticker bg-surface h-72 overflow-hidden">
              <SnapshotGraph graph={s.graph} me={me.id} />
            </div>
          </li>
        ))}
      </ul>
      <Link href="/" className="text-action-text font-semibold underline">
        Home
      </Link>
    </Screen>
  );
}
