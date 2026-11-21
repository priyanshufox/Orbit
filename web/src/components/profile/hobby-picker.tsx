"use client";

import { useState } from "react";

import { MarkerCircle } from "@/components/ui";
import type { components } from "@/lib/api/types";

type Hobby = NonNullable<components["schemas"]["SignUp"]["hobbies"]>[number];

// Same list and order as api/src/orbit/modules/accounts/hobbies.py (the API rejects others).
export const HOBBIES = [
  "Cricket",
  "Football",
  "Fitness",
  "Gaming",
  "Music",
  "Dancing",
  "Movies",
  "Anime",
  "Reading",
  "Writing",
  "Cooking",
  "Food",
  "Travel",
  "Photography",
  "Art",
  "Tech",
  "Fashion",
  "Trekking",
] as const satisfies readonly Hobby[];
export const MAX_HOBBIES = 6;

/** Toggle chips; submits as repeated `hobbies` form fields. */
export function HobbyPicker({ initial }: { initial: string[] }) {
  const [picked, setPicked] = useState<string[]>(
    initial.filter((h) => HOBBIES.includes(h as Hobby)),
  );
  const full = picked.length >= MAX_HOBBIES;

  return (
    <fieldset className="space-y-2">
      <legend className="font-heading text-xs font-extrabold tracking-wider uppercase">
        Hobbies{" "}
        <span className="font-accent text-foreground/70 text-sm font-normal tracking-normal normal-case italic">
          pick up to {MAX_HOBBIES} · {picked.length} chosen
        </span>
      </legend>
      <div className="flex flex-wrap gap-2 pt-1">
        {HOBBIES.map((h) => {
          const on = picked.includes(h);
          return (
            <button
              key={h}
              type="button"
              aria-pressed={on}
              disabled={!on && full}
              onClick={() => setPicked((p) => (on ? p.filter((x) => x !== h) : [...p, h]))}
              className={`border-ink relative rounded-full border-2 px-3 py-1.5 text-sm font-medium disabled:opacity-40 ${
                on ? "bg-highlight text-on-highlight" : "bg-surface hover:bg-foreground/5"
              }`}
            >
              {on && "✓ "}
              {h}
              {on && <MarkerCircle />}
            </button>
          );
        })}
      </div>
      {picked.map((h) => (
        <input key={h} type="hidden" name="hobbies" value={h} />
      ))}
    </fieldset>
  );
}
