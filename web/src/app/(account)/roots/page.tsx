import { Suspense } from "react";

import { Heading, Loading, Panel, Screen } from "@/components/ui";
import { requireStage, safeNext } from "@/lib/onboarding";

import { RootsForm } from "./roots-form";

export default function RootsPage(props: PageProps<"/roots">) {
  return (
    <Suspense fallback={<Loading />}>
      <RootsEditor searchParams={props.searchParams} />
    </Suspense>
  );
}

async function RootsEditor({
  searchParams,
}: {
  searchParams: PageProps<"/roots">["searchParams"];
}) {
  const next = safeNext((await searchParams).next);
  const { api } = await requireStage("ready");
  const { data: roots } = await api.GET("/me/roots");
  return (
    <Screen tone="brand">
      <Panel>
        <Heading
          title="Your roots"
          lead="Optional. If you share a school or city with someone in the room, it adds to your closeness. Others only ever see “Shared roots”, never the names."
        />
        <RootsForm
          roots={roots ?? { birth_city: null, school: null, childhood_cities: [] }}
          next={next}
        />
      </Panel>
    </Screen>
  );
}
