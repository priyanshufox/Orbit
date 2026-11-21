"use client";

/** Send a browser error to /api/client-error (task 10.3). Message and stack only, no user data. */
export function reportError(error: Error & { digest?: string }, where: string) {
  try {
    const body = JSON.stringify({
      where,
      message: String(error.message).slice(0, 500),
      digest: error.digest,
      stack: String(error.stack ?? "").slice(0, 4000),
      path: window.location.pathname,
    });
    const sent = navigator.sendBeacon?.("/api/client-error", body);
    if (!sent) void fetch("/api/client-error", { method: "POST", body, keepalive: true });
  } catch {
    // reporting must never throw
  }
}
