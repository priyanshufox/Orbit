/**
 * Development-only one-click sign-in for the seeded dev users (roadmap 2.2).
 *
 * Runs the real magic-link flow: asks Better Auth to send a link, takes it from the dev mailbox
 * (lib/email.ts) instead of an inbox, and redirects the browser to it. Disabled in production
 * and for any address outside the reserved .test domain.
 */
import { headers } from "next/headers";
import { NextResponse, type NextRequest } from "next/server";

import { auth } from "@/lib/auth";
import { takeDevMagicLink } from "@/lib/email";

export async function GET(request: NextRequest) {
  const email = request.nextUrl.searchParams.get("email") ?? "";
  if (process.env.NODE_ENV === "production" || !/^[\w.+-]+@orbit\.test$/.test(email)) {
    return new NextResponse("Not found", { status: 404 });
  }

  await auth.api.signInMagicLink({ body: { email, callbackURL: "/" }, headers: await headers() });
  const link = takeDevMagicLink(email);
  if (!link) return new NextResponse("No dev magic link was produced", { status: 500 });
  return NextResponse.redirect(link);
}
