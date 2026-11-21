"use client";

import { useState } from "react";

import { api } from "@/lib/api/browser";
import type { Member } from "@/lib/room/types";

export function Avatar({
  m,
  size = "md",
}: {
  m: Pick<Member, "name" | "avatar_url">;
  size?: "md" | "lg";
}) {
  const cls =
    size === "lg"
      ? "h-20 w-20 text-3xl border-[3px] shadow-hard-sm"
      : "h-10 w-10 text-base border-[2.5px]";
  return m.avatar_url ? (
    // eslint-disable-next-line @next/next/no-img-element
    <img src={m.avatar_url} alt="" className={`${cls} border-ink rounded-full object-cover`} />
  ) : (
    <span
      className={`${cls} border-ink bg-highlight text-on-highlight font-display grid place-items-center rounded-full`}
    >
      {m.name.slice(0, 1).toUpperCase()}
    </span>
  );
}

/** Other players, with follow / like buttons (task 4.7). */
export function People({ code, members, me }: { code: string; members: Member[]; me: string }) {
  const [sent, setSent] = useState<Record<string, true>>({});
  async function send(to: string, kind: "follow" | "like_profile") {
    const k = `${kind}:${to}`;
    setSent((s) => ({ ...s, [k]: true }));
    const { response } = await api.POST("/rooms/{code}/social", {
      params: { path: { code } },
      body: { to_user: to, kind },
    });
    if (!response.ok && response.status !== 409)
      setSent(
        (s) =>
          Object.fromEntries(Object.entries(s).filter(([key]) => key !== k)) as Record<
            string,
            true
          >,
      );
  }
  const others = members.filter((m) => m.user_id !== me);
  if (!others.length) return <p className="text-foreground/60 text-sm">Nobody else yet.</p>;
  return (
    <ul className="space-y-3">
      {others.map((m) => (
        <li
          key={m.user_id}
          className="border-ink bg-surface flex items-center gap-3 rounded-[8px] border-2 px-3 py-2"
        >
          <Avatar m={m} />
          <span className="flex-1 truncate font-medium">{m.name}</span>
          <button
            onClick={() => send(m.user_id, "like_profile")}
            disabled={sent[`like_profile:${m.user_id}`]}
            className="hover:bg-highlight hover:text-on-highlight text-action-text rounded-[6px] px-2 py-1 text-lg disabled:opacity-60"
            aria-label={`Like ${m.name}'s profile`}
          >
            {sent[`like_profile:${m.user_id}`] ? "♥" : "♡"}
          </button>
          <button
            onClick={() => send(m.user_id, "follow")}
            disabled={sent[`follow:${m.user_id}`]}
            className="border-ink press font-heading bg-background hover:bg-highlight hover:text-on-highlight shadow-hard-xs rounded-[6px] border-2 px-3 py-1 text-xs font-extrabold tracking-wide uppercase disabled:opacity-60"
          >
            {sent[`follow:${m.user_id}`] ? "Following" : "Follow"}
          </button>
        </li>
      ))}
    </ul>
  );
}
