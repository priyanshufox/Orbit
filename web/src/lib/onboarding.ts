/**
 * Where a visitor belongs in the sign-in flow:
 * signin -> age (age gate) -> consent -> ready. Roots are optional and offered after consent.
 */
import { redirect } from "next/navigation";

import { type Me, type ServerApi, serverApi } from "@/lib/api/server";

export type Stage = "signin" | "age" | "consent" | "ready";

export const STAGE_PATH: Record<Stage, string> = {
  signin: "/signin",
  age: "/signup",
  consent: "/consent",
  ready: "/",
};

type SignedIn<S extends Stage> = { stage: S; api: ServerApi; me: Me };

export type Visitor =
  | { stage: "signin"; api: null; me: null }
  | SignedIn<"age">
  | SignedIn<"consent">
  | SignedIn<"ready">;

export async function getVisitor(): Promise<Visitor> {
  const api = await serverApi();
  if (!api) return { stage: "signin", api: null, me: null };
  const { data: me, error, response } = await api.GET("/me");
  if (!me) {
    throw new Error(`Orbit API /me failed (${response.status}): ${JSON.stringify(error)}`);
  }
  const stage = !me.onboarded ? "age" : !me.consented ? "consent" : "ready";
  return { stage, api, me };
}

/** A same-site path to come back to after onboarding (e.g. /play/ABC234), or null. */
export function safeNext(value: unknown): string | null {
  return typeof value === "string" && value.startsWith("/") && !value.startsWith("//")
    ? value
    : null;
}

export function withNext(path: string, next: string | null | undefined): string {
  return next ? `${path}${path.includes("?") ? "&" : "?"}next=${encodeURIComponent(next)}` : path;
}

/** Send the visitor to their current step unless it is one of `allowed`. `next` is carried
 * through sign-in and onboarding, and used once the visitor is ready. */
export async function requireStage<S extends Stage>(
  allowed: S | S[],
  next?: string | null,
): Promise<Extract<Visitor, { stage: S }>> {
  const ok = (Array.isArray(allowed) ? allowed : [allowed]) as Stage[];
  const visitor = await getVisitor();
  if (!ok.includes(visitor.stage)) {
    redirect(visitor.stage === "ready" && next ? next : withNext(STAGE_PATH[visitor.stage], next));
  }
  return visitor as Extract<Visitor, { stage: S }>;
}
