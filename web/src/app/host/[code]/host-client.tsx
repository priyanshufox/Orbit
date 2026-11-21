"use client";

import QRCode from "qrcode";
import { useEffect, useMemo, useState } from "react";

import { COMMUNITY_COLOURS, GraphView, type GraphEdge } from "@/components/graph/graph-view";
import { EdgeDetails } from "@/components/room/edge-details";
import { Avatar } from "@/components/room/people";
import { Button, ErrorText, Sparkles, Tag } from "@/components/ui";
import { api } from "@/lib/api/browser";
import { mmss, useCountdown } from "@/lib/room/hooks";
import { useRoom } from "@/lib/room/use-room";

/** The big screen (tasks 3.6, 4.8, 7.2). Shown on a TV or laptop signed in as the host. */
export function HostClient({ code, me }: { code: string; me: string }) {
  const { room, error, graph, closingAt, socket } = useRoom(code, me);
  const [qr, setQr] = useState<string | null>(null);
  const [startError, setStartError] = useState<string | null>(null);
  const [selected, setSelected] = useState<GraphEdge | null>(null);
  const joinUrl = typeof window === "undefined" ? "" : `${window.location.origin}/play/${code}`;
  const left = useCountdown(room?.ends_at);

  useEffect(() => {
    if (joinUrl) QRCode.toDataURL(joinUrl, { width: 560, margin: 1 }).then(setQr);
  }, [joinUrl]);

  const names = useMemo(
    () => Object.fromEntries((graph?.nodes ?? []).map((n) => [n.id, n.name])),
    [graph],
  );

  if (error) return <Centered title="Room not found" lead={error} />;
  if (!room) return <Centered title="Loading…" />;
  if (!room.is_host)
    return <Centered title="Host screen" lead="Only the room's host can open this screen." />;

  async function start() {
    setStartError(null);
    const { response } = await api.POST("/rooms/{code}/start", { params: { path: { code } } });
    if (!response.ok) setStartError("Need at least two players in the room to start.");
  }
  async function kick(userId: string, name: string) {
    if (!confirm(`Remove ${name}? Their data in this room is deleted and they can't rejoin.`))
      return;
    await api.POST("/rooms/{code}/kick", { params: { path: { code } }, body: { user_id: userId } });
  }

  const finished = room.members.filter((m) => m.finished).length;
  const status = (
    <p className="font-heading text-xs font-extrabold tracking-wider uppercase opacity-75">
      {socket === "live" ? "● Live" : "○ Reconnecting…"}
      {closingAt && ` · Room data is deleted at ${new Date(closingAt).toLocaleTimeString()}`}
    </p>
  );

  if (room.state === "CREATED" || room.state === "LOBBY") {
    // Brand screen: green grid; body text stays on cream panels.
    return (
      <main className="bg-grid grain grid flex-1 items-center gap-10 p-8 lg:grid-cols-[auto_1fr] lg:p-14">
        <section className="sticker bg-background flex rotate-[-1deg] flex-col items-center gap-4 p-6">
          {qr && (
            // eslint-disable-next-line @next/next/no-img-element
            <img
              src={qr}
              alt={`QR code to join room ${code}`}
              className="border-ink w-72 rounded-[8px] border-[3px] bg-white p-3 lg:w-96"
            />
          )}
          <p className="text-foreground/75 text-lg">Scan to join, or go to</p>
          <p className="font-heading text-xl font-extrabold">
            {joinUrl.replace(/^https?:\/\//, "").replace(/\/play\/.*/, "")}/play
          </p>
          <p className="bg-highlight text-on-highlight border-ink shadow-hard-sm font-display rounded-[8px] border-[3px] px-5 py-1 text-6xl tracking-[0.15em] lg:text-7xl">
            {code}
          </p>
        </section>
        <section className="sticker bg-background flex min-h-[70%] flex-col gap-6 p-8">
          <h1 className="font-display text-5xl leading-none uppercase lg:text-7xl">
            Who&apos;s in your orbit?
          </h1>
          <Tag>
            {room.members.length} of {room.member_cap} players
          </Tag>
          <ul className="flex flex-wrap gap-5">
            {room.members.map((m) => (
              <li
                key={m.user_id}
                className="group animate-pop relative flex w-24 flex-col items-center gap-2"
              >
                <Avatar m={m} size="lg" />
                <span className="w-full truncate text-center font-semibold">{m.name}</span>
                <button
                  onClick={() => kick(m.user_id, m.name)}
                  className="bg-surface border-ink absolute -top-1 -right-1 hidden h-7 w-7 rounded-full border-2 text-sm group-hover:block"
                  aria-label={`Remove ${m.name}`}
                >
                  ×
                </button>
              </li>
            ))}
          </ul>
          <div className="mt-auto max-w-sm space-y-3">
            <ErrorText>{startError}</ErrorText>
            <Button onClick={start} disabled={room.members.length < 2}>
              Start the 5-minute round
            </Button>
            <a
              href={`/play/${code}`}
              target="_blank"
              rel="noreferrer"
              className="text-foreground/75 block text-center text-sm underline"
            >
              Play on this device too
            </a>
            {status}
          </div>
        </section>
      </main>
    );
  }

  if (room.state === "PLAYING") {
    return (
      <main className="flex flex-1 flex-col items-center justify-center gap-10 p-10">
        <p
          className={`font-display text-[10rem] leading-none tabular-nums ${left !== null && left < 30 ? "text-danger" : ""}`}
        >
          {left !== null ? mmss(left) : "…"}
        </p>
        <div className="w-full max-w-3xl space-y-4">
          <div className="border-ink bg-surface shadow-hard-sm h-10 overflow-hidden rounded-full border-[3px]">
            <div
              className="bg-highlight border-ink h-full border-r-[3px] transition-all duration-[240ms]"
              style={{
                width: `${room.members.length ? (finished / room.members.length) * 100 : 0}%`,
              }}
            />
          </div>
          <p className="font-heading text-center text-2xl font-extrabold uppercase">
            {finished} of {room.members.length} finished
          </p>
        </div>
        <ul className="flex flex-wrap justify-center gap-5">
          {room.members.map((m) => (
            <li
              key={m.user_id}
              className={`flex flex-col items-center gap-1 ${m.finished ? "" : "opacity-40"}`}
            >
              <Avatar m={m} size="lg" />
              <span className="font-semibold">
                {m.finished ? "✓ " : ""}
                {m.name}
              </span>
            </li>
          ))}
        </ul>
        {status}
      </main>
    );
  }

  if (room.state === "SCORING" || !graph) {
    return (
      <Centered title="Who's close?" lead="Comparing answers, reactions, roots and follows." />
    );
  }

  const communities = [...new Set(graph.nodes.map((n) => n.community))].sort();
  return (
    <main className="relative flex flex-1 flex-col">
      <header className="flex flex-wrap items-center justify-between gap-4 pt-6 pr-32 pl-8">
        <div className="flex items-center gap-4">
          <h1 className="font-display text-6xl leading-none uppercase">Room {code}</h1>
          <Sparkles />
        </div>
        <div className="sticker-sm bg-surface flex flex-wrap gap-4 px-4 py-2 text-lg font-semibold">
          {communities.map((c) => (
            <span key={c} className="flex items-center gap-2">
              <span
                className="border-ink h-5 w-5 rounded-full border-2"
                style={{ background: COMMUNITY_COLOURS[c % COMMUNITY_COLOURS.length] }}
              />
              Group {c + 1}
            </span>
          ))}
          <span className="flex items-center gap-2">
            <span className="border-tomato-700 h-0 w-8 border-t-[3px] border-dashed" /> follows
          </span>
        </div>
      </header>
      <div className="relative flex-1">
        <div className="absolute inset-0">
          <GraphView data={graph} size="tv" onSelectEdge={setSelected} />
        </div>
        {selected && (
          <div className="absolute right-8 bottom-8 w-96">
            <EdgeDetails edge={selected} names={names} onClose={() => setSelected(null)} />
          </div>
        )}
      </div>
      <footer className="px-8 pb-4">{status}</footer>
    </main>
  );
}

function Centered({ title, lead }: { title: string; lead?: string }) {
  return (
    <main className="flex flex-1 flex-col items-center justify-center gap-6 p-10 text-center">
      <h1 className="font-display text-8xl leading-none uppercase">{title}</h1>
      {lead && <p className="text-foreground/75 text-2xl">{lead}</p>}
      <div className="border-ink border-t-highlight h-16 w-16 animate-spin rounded-full border-[5px]" />
    </main>
  );
}
