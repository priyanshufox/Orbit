"use client";

import { useState } from "react";

import { Button, ErrorText, Field } from "@/components/ui";
import { authClient } from "@/lib/auth-client";

function GoogleMark() {
  return (
    <svg viewBox="0 0 48 48" className="h-5 w-5" aria-hidden>
      <path
        fill="#FFC107"
        d="M43.6 20.5H42V20H24v8h11.3C33.7 32.7 29.2 36 24 36c-6.6 0-12-5.4-12-12s5.4-12 12-12c3.1 0 5.8 1.2 7.9 3.1l5.7-5.7C34 6.1 29.3 4 24 4 12.9 4 4 12.9 4 24s8.9 20 20 20 20-8.9 20-20c0-1.3-.1-2.4-.4-3.5z"
      />
      <path
        fill="#FF3D00"
        d="M6.3 14.7l6.6 4.8C14.7 15.1 19 12 24 12c3.1 0 5.8 1.2 7.9 3.1l5.7-5.7C34 6.1 29.3 4 24 4 16.3 4 9.7 8.3 6.3 14.7z"
      />
      <path
        fill="#4CAF50"
        d="M24 44c5.2 0 9.9-2 13.4-5.2l-6.2-5.2C29.2 35.1 26.7 36 24 36c-5.2 0-9.6-3.3-11.3-8l-6.5 5C9.5 39.6 16.2 44 24 44z"
      />
      <path
        fill="#1976D2"
        d="M43.6 20.5H42V20H24v8h11.3c-.8 2.2-2.2 4.2-4.1 5.6l6.2 5.2C37 39.2 44 34 44 24c0-1.3-.1-2.4-.4-3.5z"
      />
    </svg>
  );
}

export function SignInForm({
  googleEnabled,
  callbackURL,
}: {
  googleEnabled: boolean;
  callbackURL: string;
}) {
  const [email, setEmail] = useState("");
  const [sentTo, setSentTo] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function google() {
    setError(null);
    if (!googleEnabled) {
      setError("Google sign-in isn't set up on this server yet. Use your email for now.");
      return;
    }
    const { error } = await authClient.signIn.social({ provider: "google", callbackURL });
    if (error) setError(error.message ?? "Google sign-in failed. Try again.");
  }

  async function sendLink(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    const { error } = await authClient.signIn.magicLink({ email, callbackURL });
    setBusy(false);
    if (error) setError(error.message ?? "Couldn't send the link. Try again.");
    else setSentTo(email);
  }

  if (sentTo) {
    return (
      <div className="border-ink bg-surface animate-pop space-y-3 rounded-[8px] border-[2.5px] p-5">
        <p className="font-heading font-extrabold uppercase">📬 Check your inbox</p>
        <p className="text-foreground/75 text-sm">
          We sent a link to <strong>{sentTo}</strong>. It works once and expires in 10 minutes. New
          here? The link creates your account.
        </p>
        <Button variant="ghost" onClick={() => setSentTo(null)}>
          Use a different email
        </Button>
      </div>
    );
  }

  return (
    <div className="space-y-5">
      <Button variant="secondary" onClick={google} className="normal-case">
        <GoogleMark />
        Continue with Google
      </Button>
      <div className="font-accent text-foreground/70 flex items-center gap-3 text-sm italic">
        <span className="bg-ink h-[2px] flex-1" /> or with email{" "}
        <span className="bg-ink h-[2px] flex-1" />
      </div>
      <form onSubmit={sendLink} className="space-y-3">
        <Field
          label="Email"
          type="email"
          name="email"
          autoComplete="email"
          required
          placeholder="you@example.com"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
        />
        <Button type="submit" disabled={busy}>
          {busy ? "Sending…" : "Email me a link"}
        </Button>
      </form>
      <ErrorText>{error}</ErrorText>
    </div>
  );
}
