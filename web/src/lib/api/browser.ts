"use client";

/**
 * Typed FastAPI client for client components (game screens, Phase 3+). Fetches a JWT from
 * Better Auth's /api/auth/token and reuses it until shortly before it expires.
 */
import createClient, { type Middleware } from "openapi-fetch";

import { API_URL } from "@/lib/api/config";
import type { paths } from "@/lib/api/types";
import { authClient } from "@/lib/auth-client";

let cached: { token: string; expiresAt: number } | null = null;

function expiryOf(token: string): number {
  const payload = JSON.parse(atob(token.split(".")[1]!.replace(/-/g, "+").replace(/_/g, "/")));
  return (payload.exp as number) * 1000;
}

export async function getApiToken(): Promise<string | null> {
  if (cached && cached.expiresAt - Date.now() > 60_000) return cached.token;
  const { data } = await authClient.token();
  if (!data?.token) return null;
  cached = { token: data.token, expiresAt: expiryOf(data.token) };
  return cached.token;
}

const withToken: Middleware = {
  async onRequest({ request }) {
    const token = await getApiToken();
    if (token) request.headers.set("Authorization", `Bearer ${token}`);
    return request;
  },
};

export const api = createClient<paths>({ baseUrl: API_URL });
api.use(withToken);
