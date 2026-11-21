import { Suspense } from "react";

import { Loading } from "@/components/ui";
import { requireStage } from "@/lib/onboarding";

import { PlayClient } from "./play-client";

export default function Page(props: PageProps<"/play/[code]">) {
  return (
    <Suspense fallback={<Loading />}>
      <Room params={props.params} />
    </Suspense>
  );
}

async function Room({ params }: { params: PageProps<"/play/[code]">["params"] }) {
  const code = (await params).code.toUpperCase();
  // Not signed in or mid-onboarding: go through sign-in/age/consent, then come back here.
  const { me } = await requireStage("ready", `/play/${code}`);
  return <PlayClient code={code} me={{ id: me.id, name: me.name }} />;
}
