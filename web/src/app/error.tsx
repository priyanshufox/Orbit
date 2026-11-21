"use client";

import { useEffect } from "react";

import { Button, Heading, Screen } from "@/components/ui";
import { reportError } from "@/lib/telemetry/report";

export default function ErrorPage({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => reportError(error, "route"), [error]);
  return (
    <Screen>
      <Heading title="Something went wrong" lead="It's been reported. Try again in a moment." />
      <Button onClick={reset}>Try again</Button>
    </Screen>
  );
}
