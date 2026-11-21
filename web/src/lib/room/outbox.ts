"use client";

/**
 * Answers and reactions survive a flaky connection (task 4.6): each write is queued in
 * localStorage, sent with retries and backoff, and removed once the API confirms. Writes are
 * idempotent PUTs keyed by card, so a later answer simply replaces an earlier one in the queue.
 */
import { api } from "@/lib/api/browser";

type Write =
  | { kind: "answer"; id: string; value: Record<string, unknown> }
  | { kind: "reaction"; id: string; reaction: "like" | "laugh" | "skip" | "send" };

const key = (room: string) => `orbit:outbox:${room}`;

function load(room: string): Record<string, Write> {
  try {
    return JSON.parse(localStorage.getItem(key(room)) ?? "{}");
  } catch {
    return {};
  }
}

function save(room: string, pending: Record<string, Write>) {
  try {
    localStorage.setItem(key(room), JSON.stringify(pending));
  } catch {
    // Private mode or full storage: the in-memory retry still runs.
  }
}

async function send(room: string, w: Write): Promise<"ok" | "retry" | "drop"> {
  try {
    const res =
      w.kind === "answer"
        ? await api.PUT("/rooms/{code}/answers/{question_id}", {
            params: { path: { code: room, question_id: w.id } },
            body: { value: w.value },
          })
        : await api.PUT("/rooms/{code}/reactions/{content_id}", {
            params: { path: { code: room, content_id: w.id } },
            body: { reaction: w.reaction },
          });
    if (res.response.ok) return "ok";
    // 4xx other than rate limiting won't succeed on retry (round over, invalid, removed).
    return res.response.status === 429 || res.response.status >= 500 ? "retry" : "drop";
  } catch {
    return "retry"; // offline / network error
  }
}

export class Outbox {
  private timer: ReturnType<typeof setTimeout> | null = null;
  private delay = 1000;
  private pending: Record<string, Write>;

  constructor(
    private room: string,
    private onChange: (pendingCount: number) => void,
  ) {
    this.pending = load(room);
    if (typeof window !== "undefined") window.addEventListener("online", () => this.flush());
    this.flush();
  }

  put(w: Write) {
    this.pending[`${w.kind}:${w.id}`] = w;
    save(this.room, this.pending);
    this.onChange(this.size());
    this.flush();
  }

  size() {
    return Object.keys(this.pending).length;
  }

  async flush() {
    if (this.timer) clearTimeout(this.timer);
    this.timer = null;
    let retry = false;
    for (const [k, w] of Object.entries(this.pending)) {
      const result = await send(this.room, w);
      if (result === "retry") {
        retry = true;
        continue;
      }
      if (this.pending[k] === w) delete this.pending[k];
    }
    save(this.room, this.pending);
    this.onChange(this.size());
    if (retry) {
      this.timer = setTimeout(() => this.flush(), this.delay);
      this.delay = Math.min(this.delay * 2, 15_000);
    } else {
      this.delay = 1000;
    }
  }
}
