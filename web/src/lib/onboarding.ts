/**
 * Where a visitor belongs in the sign-in flow:
 * signin -> age (age gate) -> consent -> ready. Roots are optional and offered after consent.
 */
import { redirect } from "next/navigation";

import { type Me, type ServerApi, serverApi } from "@/lib/api/server";

export type Stage = "signin" | "age" | "consent" | "ready";

export const STAGE_PATH: Record<Stage, string> = {
  signin: "/signin",
  age: "/age",
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

/** Send the visitor to their current step unless it is one of `allowed`. */
export async function requireStage<S extends Stage>(
  ...allowed: S[]
): Promise<Extract<Visitor, { stage: S }>> {
  const visitor = await getVisitor();
  if (!(allowed as Stage[]).includes(visitor.stage)) redirect(STAGE_PATH[visitor.stage]);
  return visitor as Extract<Visitor, { stage: S }>;
}
