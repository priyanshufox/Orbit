"use client";

import { useActionState } from "react";

import { ErrorText } from "@/components/ui";
import { goToRoom } from "@/lib/actions";

/** Code input and button on one row. */
export function JoinForm() {
  const [state, action, pending] = useActionState(goToRoom, undefined);
  return (
    <form action={action} className="space-y-2">
      <label
        htmlFor="room-code"
        className="font-heading text-xs font-extrabold tracking-wider uppercase"
      >
        Join with a code
      </label>
      <div className="flex gap-2">
        <input
          id="room-code"
          name="code"
          autoComplete="off"
          autoCapitalize="characters"
          maxLength={6}
          placeholder="ABC234"
          defaultValue={state?.values?.code}
          className="border-ink bg-surface placeholder:text-foreground/40 focus:ring-highlight h-12 min-w-0 flex-1 rounded-[8px] border-[2.5px] px-4 font-mono text-lg tracking-[0.2em] uppercase outline-none focus:ring-4"
        />
        <button
          type="submit"
          disabled={pending}
          className="border-ink bg-surface font-heading hover:bg-highlight hover:text-on-highlight rounded-[8px] border-[2.5px] px-5 text-sm font-extrabold tracking-wider uppercase disabled:opacity-50"
        >
          Join
        </button>
      </div>
      <ErrorText>{state?.error}</ErrorText>
    </form>
  );
}
