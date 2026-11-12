/**
 * Typed FastAPI client for server components and server actions.
 *
 * Each request carries a short-lived JWT minted by Better Auth for the signed-in user; FastAPI
 * verifies it against /api/auth/jwks (no shared secret).
 */
import createClient from "openapi-fetch";
import { headers } from "next/headers";

import { API_URL } from "@/lib/api/config";
import type { components, paths } from "@/lib/api/types";
import { auth } from "@/lib/auth";

export type Me = components["schemas"]["Me"];
export type Roots = components["schemas"]["Roots"];

export type ServerApi = ReturnType<typeof createClient<paths>>;

/** An API client acting as the current user, or null when nobody is signed in. */
export async function serverApi(): Promise<ServerApi | null> {
  const requestHeaders = await headers();
  const session = await auth.api.getSession({ headers: requestHeaders });
  if (!session) return null;
  const { token } = await auth.api.getToken({ headers: requestHeaders });
  return createClient<paths>({
    baseUrl: API_URL,
    headers: { Authorization: `Bearer ${token}` },
    cache: "no-store",
  });
}
