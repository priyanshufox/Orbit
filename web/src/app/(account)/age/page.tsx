import { Suspense } from "react";

import { Heading, Loading, Screen } from "@/components/ui";
import { requireStage } from "@/lib/onboarding";

import { AgeForm } from "./age-form";

export default function AgePage() {
  return (
    <Suspense fallback={<Loading />}>
      <AgeGate />
    </Suspense>
  );
}

async function AgeGate() {
  const { me } = await requireStage("age");
  return (
    <Screen>
      <Heading title={`Hi ${me.name}`} lead="First, how old are you?" />
      <AgeForm />
    </Screen>
  );
}
