/**
 * Magic-link delivery. Uses Resend's HTTP API when RESEND_API_KEY is set; otherwise, outside
 * production only, prints the link to the server console and remembers it for the dev login.
 */

const devLinks = ((globalThis as { __orbitDevLinks?: Map<string, string> }).__orbitDevLinks ??=
  new Map<string, string>());

/** The most recent magic link sent to `email` in development. */
export function takeDevMagicLink(email: string): string | undefined {
  const url = devLinks.get(email);
  devLinks.delete(email);
  return url;
}

export async function sendMagicLinkEmail(email: string, url: string): Promise<void> {
  const apiKey = process.env.RESEND_API_KEY;
  if (!apiKey) {
    if (process.env.NODE_ENV === "production") {
      throw new Error("RESEND_API_KEY is not set; cannot send sign-in email.");
    }
    devLinks.set(email, url);
    console.info(`[dev] Magic link for ${email}: ${url}`);
    return;
  }

  const res = await fetch("https://api.resend.com/emails", {
    method: "POST",
    headers: { Authorization: `Bearer ${apiKey}`, "Content-Type": "application/json" },
    body: JSON.stringify({
      from: process.env.EMAIL_FROM,
      to: email,
      subject: "Your Orbit sign-in link",
      text: `Tap to sign in to Orbit:\n\n${url}\n\nThe link works once and expires in 10 minutes.`,
    }),
  });
  if (!res.ok) {
    throw new Error(`Sign-in email failed: ${res.status}`);
  }
}
