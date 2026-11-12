"use client";

import { useState } from "react";

import { Button, ErrorText, Field } from "@/components/ui";
import { authClient } from "@/lib/auth-client";

export function SignInForm({ googleEnabled, isDev }: { googleEnabled: boolean; isDev: boolean }) {
  const [email, setEmail] = useState("");
  const [sentTo, setSentTo] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function sendLink(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    const { error } = await authClient.signIn.magicLink({ email, callbackURL: "/" });
    setBusy(false);
    if (error) setError(error.message ?? "Couldn't send the link. Try again.");
    else setSentTo(email);
  }

  if (sentTo) {
    return (
      <div className="border-foreground/10 space-y-3 rounded-2xl border p-5">
        <p className="font-medium">Check your inbox</p>
        <p className="text-foreground/70 text-sm">
          We sent a sign-in link to <strong>{sentTo}</strong>. It works once and expires in 10
          minutes.
          {isDev && " In development, the link is printed in the web server's console."}
        </p>
        <Button variant="ghost" onClick={() => setSentTo(null)}>
          Use a different email
        </Button>
      </div>
    );
  }

  return (
    <div className="space-y-5">
      {googleEnabled && (
        <>
          <Button
            variant="secondary"
            onClick={() => authClient.signIn.social({ provider: "google", callbackURL: "/" })}
          >
            Continue with Google
          </Button>
          <div className="text-foreground/50 flex items-center gap-3 text-xs">
            <span className="bg-foreground/10 h-px flex-1" /> or{" "}
            <span className="bg-foreground/10 h-px flex-1" />
          </div>
        </>
      )}

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
        <ErrorText>{error}</ErrorText>
        <Button type="submit" disabled={busy}>
          {busy ? "Sending…" : "Email me a sign-in link"}
        </Button>
      </form>
    </div>
  );
}
