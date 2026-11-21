"use client";

import { useEffect } from "react";

import { reportError } from "@/lib/telemetry/report";

export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => reportError(error, "global"), [error]);
  return (
    <html lang="en">
      <body
        style={{ fontFamily: "sans-serif", padding: 32, background: "#0a0a0a", color: "#ededed" }}
      >
        <h1>Something went wrong</h1>
        <p>It&apos;s been reported. Try again in a moment.</p>
        <button onClick={reset}>Try again</button>
      </body>
    </html>
  );
}
