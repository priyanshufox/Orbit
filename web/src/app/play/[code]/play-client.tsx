"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useMemo, useState } from "react";

import { GraphView, pct, type GraphEdge } from "@/components/graph/graph-view";
import { Deck } from "@/components/room/deck";
import { EdgeDetails } from "@/components/room/edge-details";
import { Avatar, People } from "@/components/room/people";
import { Button, ErrorText, Heading, Panel, Screen, Sparkles, Starburst } from "@/components/ui";
import { api } from "@/lib/api/browser";
import { mmss, useCountdown } from "@/lib/room/hooks";
import type { DeckView } from "@/lib/room/types";
import { useRoom } from "@/lib/room/use-room";

export function PlayClient({ code, me }: { code: string; me: { id: string; name: string } }) {
  const { room, error, graph, closingAt, removed, reload, setRoom } = useRoom(code, me.id);
  const [joinError, setJoinError] = useState<string | null>(null);
  const [joining, setJoining] = useState(false);
  const router = useRouter();

  const join = useCallback(async () => {
    setJoining(true);
    const { data, error: err } = await api.POST("/rooms/{code}/join", {
      params: { path: { code } },
    });
    setJoining(false);
    if (data) setRoom(data);
    else {
      const detail = (err as { detail?: string } | undefined)?.detail;
      setJoinError(
        detail === "room_full"
          ? "This room is full."
          : detail === "round_over"
            ? "This round is already over."
            : detail === "kicked"
              ? "The host removed you from this room."
              : detail === "rate_limited"
                ? "Too many tries. Wait a minute."
                : "Couldn't join. Try again.",
      );
    }
  }, [code, setRoom]);

  async function leave() {
    if (!confirm("Leave this room? Your answers, reactions and follows in it are deleted.")) return;
    await api.POST("/rooms/{code}/leave", { params: { path: { code } } });
    router.push("/");
  }

  if (removed) {
    return (
      <Screen>
        <Heading
          title="You're out of this room"
          lead="Your data from this room has been deleted."
        />
        <Link href="/" className="text-action-text font-semibold underline">
          Home
        </Link>
      </Screen>
    );
  }
  if (error)
    return (
      <Screen>
        <Heading title="Room not found" lead={error} />
      </Screen>
    );
  if (!room)
    return (
      <Screen>
        <p className="text-foreground/60">Loading room…</p>
      </Screen>
    );

  const banner = closingAt && (
    <p className="sticker-sm bg-highlight text-on-highlight px-4 py-2 text-sm">
      ⏳ This room and its data are deleted at {new Date(closingAt).toLocaleTimeString()}. Your own
      graph is saved to your history.
    </p>
  );

  if (!room.is_member) {
    const open = ["CREATED", "LOBBY", "PLAYING"].includes(room.state);
    return (
      <Screen tone="brand">
        <Panel>
          <Heading
            tag="You've been invited"
            title={`Room ${room.code}`}
            lead={
              open
                ? `${room.members.length} of ${room.member_cap} players are in. Join to play.`
                : "This round is over."
            }
          />
          <div className="flex -space-x-3">
            {room.members.slice(0, 8).map((m) => (
              <Avatar key={m.user_id} m={m} />
            ))}
          </div>
          <ErrorText>{joinError}</ErrorText>
          {open && (
            <Button onClick={join} disabled={joining}>
              {joining ? "Joining…" : `Join as ${me.name}`}
            </Button>
          )}
        </Panel>
      </Screen>
    );
  }

  const mine = room.members.find((m) => m.user_id === me.id);

  if (room.state === "CREATED" || room.state === "LOBBY") {
    return (
      <Screen>
        {banner}
        <Heading
          display
          tag="Lobby"
          title="You're in!"
          lead="Waiting for the host to start. The round takes 5 minutes."
        />
        <section className="space-y-3">
          <p className="font-heading text-xs font-extrabold tracking-wider uppercase">
            {room.members.length} players
          </p>
          <People code={code} members={room.members} me={me.id} />
        </section>
        <Button variant="ghost" onClick={leave}>
          Leave and delete my data
        </Button>
      </Screen>
    );
  }

  if (room.state === "PLAYING") {
    return mine?.finished ? (
      <Waiting room={room} />
    ) : (
      <Screen>
        <PlayingDeck
          code={code}
          onFinish={async () => {
            await api.POST("/rooms/{code}/finish", { params: { path: { code } } });
            reload();
          }}
        />
      </Screen>
    );
  }

  if (room.state === "SCORING") {
    return (
      <Screen>
        <Heading
          display
          title="Who's close?"
          lead="Comparing answers, reactions, roots and follows. The graph appears in a few seconds."
        />
        <div className="border-ink border-t-highlight h-12 w-12 animate-spin self-center rounded-full border-4" />
      </Screen>
    );
  }

  return (
    <Reveal
      code={code}
      me={me.id}
      members={room.members}
      graph={graph}
      banner={banner}
      onLeave={leave}
    />
  );
}

function PlayingDeck({ code, onFinish }: { code: string; onFinish: () => void }) {
  const [deck, setDeck] = useState<DeckView | null>(null);
  useEffect(() => {
    api
      .GET("/rooms/{code}/deck", { params: { path: { code } } })
      .then(({ data }) => data && setDeck(data));
  }, [code]);
  if (!deck) return <p className="text-foreground/60">Shuffling the deck…</p>;
  return <Deck code={code} deck={deck} onFinish={onFinish} />;
}

function Waiting({ room }: { room: NonNullable<ReturnType<typeof useRoom>["room"]> }) {
  const left = useCountdown(room.ends_at);
  const done = room.members.filter((m) => m.finished).length;
  return (
    <Screen>
      <Sparkles />
      <Heading
        display
        title="Nice! You're done."
        lead="Waiting for the others. The graph appears when everyone finishes or time runs out."
      />
      <p className="sticker-sm bg-surface font-heading px-4 py-3 text-sm font-extrabold tracking-wide uppercase">
        {done} of {room.members.length} finished{left !== null && ` · ${mmss(left)} left`}
      </p>
    </Screen>
  );
}

function Reveal({
  code,
  me,
  members,
  graph,
  banner,
  onLeave,
}: {
  code: string;
  me: string;
  members: { user_id: string; name: string; avatar_url: string | null; finished: boolean }[];
  graph: ReturnType<typeof useRoom>["graph"];
  banner: React.ReactNode;
  onLeave: () => void;
}) {
  const [selected, setSelected] = useState<GraphEdge | null>(null);
  const names = useMemo(
    () => Object.fromEntries((graph?.nodes ?? []).map((n) => [n.id, n.name])),
    [graph],
  );
  const mine = useMemo(
    () =>
      (graph?.edges ?? [])
        .filter((e) => e.a === me || e.b === me)
        .sort((x, y) => y.total - x.total),
    [graph, me],
  );
  if (!graph)
    return (
      <Screen>
        <p className="text-foreground/60">Loading the graph…</p>
      </Screen>
    );

  return (
    <main className="mx-auto flex w-full max-w-2xl flex-1 flex-col gap-5 px-4 py-6">
      {banner}
      <div className="flex items-center gap-3">
        <h1 className="font-display text-5xl uppercase">Your orbit</h1>
        <Sparkles />
      </div>
      <div className="sticker bg-surface relative h-[60vh] min-h-80 overflow-hidden">
        <GraphView data={graph} me={me} onSelectEdge={setSelected} />
        {selected && (
          <div className="absolute inset-x-3 bottom-3">
            <EdgeDetails edge={selected} names={names} onClose={() => setSelected(null)} />
          </div>
        )}
      </div>

      <section className="space-y-2">
        <h2 className="font-heading text-lg font-extrabold uppercase">Closest to you</h2>
        {mine.length === 0 && (
          <p className="text-foreground/60 text-sm">No strong connections this round.</p>
        )}
        <ol className="space-y-3 pt-4">
          {mine.map((e, rank) => {
            const other = e.a === me ? e.b : e.a;
            return (
              <li key={other} className="relative">
                {rank === 0 && <Starburst className="absolute -top-6 -left-5 z-10">Top!</Starburst>}
                <button
                  onClick={() => setSelected(e)}
                  className={`sticker-sm press bg-surface hover:bg-highlight hover:text-on-highlight flex w-full items-center justify-between gap-3 py-3 pr-4 text-left ${rank === 0 ? "pl-12" : "pl-4"}`}
                >
                  <span>
                    <span className="font-heading font-extrabold">{names[other]}</span>
                    {e.reasons[0] && (
                      <span className="text-foreground/75 block text-xs">{e.reasons[0].text}</span>
                    )}
                  </span>
                  <span className="font-display text-2xl tabular-nums">{pct(e.total)}</span>
                </button>
              </li>
            );
          })}
        </ol>
      </section>

      <section className="space-y-2">
        <h2 className="font-heading text-lg font-extrabold uppercase">Follow people</h2>
        <People code={code} members={members} me={me} />
      </section>
      <div className="flex justify-between text-sm">
        <Link href="/" className="text-action-text font-semibold underline">
          Home
        </Link>
        <button onClick={onLeave} className="text-foreground/75 underline">
          Leave and delete my data
        </button>
      </div>
    </main>
  );
}
