/**
 * Better Auth server instance (sign-in identity only).
 *
 * Identity lives in the Postgres schema "auth" (tables created by an Alembic migration in api/).
 * Orbit's own profile row in public.users is created by the API after the age gate, with the
 * same id. The API trusts the short-lived JWTs issued here, verified against /api/auth/jwks.
 */
import { betterAuth } from "better-auth";
import { nextCookies } from "better-auth/next-js";
import { jwt, magicLink } from "better-auth/plugins";
import { Pool } from "pg";

import { sendMagicLinkEmail } from "@/lib/email";

// One pool per server process, surviving dev hot reloads.
const pool = ((globalThis as { __orbitAuthPool?: Pool }).__orbitAuthPool ??= new Pool({
  connectionString: process.env.AUTH_DATABASE_URL,
  options: "-c search_path=auth",
}));

const googleId = process.env.GOOGLE_CLIENT_ID;
const googleSecret = process.env.GOOGLE_CLIENT_SECRET;

export const googleEnabled = Boolean(googleId && googleSecret);

export const auth = betterAuth({
  baseURL: process.env.BETTER_AUTH_URL,
  database: pool,
  advanced: { database: { generateId: "uuid" } },
  socialProviders: googleEnabled
    ? { google: { clientId: googleId!, clientSecret: googleSecret!, prompt: "select_account" } }
    : {},
  plugins: [
    magicLink({
      expiresIn: 600,
      sendMagicLink: async ({ email, url }) => sendMagicLinkEmail(email, url),
    }),
    jwt({
      jwt: {
        expirationTime: "15m",
        // Only what the API needs; subject (user id), iss and aud are set by the plugin.
        definePayload: ({ user }) => ({ email: user.email, name: user.name, picture: user.image }),
      },
    }),
    nextCookies(), // must stay last
  ],
});
