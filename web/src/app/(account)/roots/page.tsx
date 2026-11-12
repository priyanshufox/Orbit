import { Suspense } from "react";

import { Heading, Loading, Screen } from "@/components/ui";
import { requireStage } from "@/lib/onboarding";

import { RootsForm } from "./roots-form";

export default function RootsPage() {
  return (
    <Suspense fallback={<Loading />}>
      <RootsEditor />
    </Suspense>
  );
}

async function RootsEditor() {
  const { api } = await requireStage("ready");
  const { data: roots } = await api.GET("/me/roots");
  return (
    <Screen>
      <Heading
        title="Your roots"
        lead="Optional. If you share a school or city with someone in the room, it adds to your closeness. Others only ever see “Shared roots”, never the names."
      />
      <RootsForm roots={roots ?? { birth_city: null, school: null, childhood_cities: [] }} />
    </Screen>
  );
}
