import { Suspense } from "react";

import { Loading } from "@/components/ui";
import { requireStage } from "@/lib/onboarding";

import { HostClient } from "./host-client";

export default function Page(props: PageProps<"/host/[code]">) {
  return (
    <Suspense fallback={<Loading />}>
      <Room params={props.params} />
    </Suspense>
  );
}

async function Room({ params }: { params: PageProps<"/host/[code]">["params"] }) {
  const code = (await params).code.toUpperCase();
  // Not signed in or mid-onboarding: go through sign-in/age/consent, then come back here.
  const { me } = await requireStage("ready", `/host/${code}`);
  return <HostClient code={code} me={me.id} />;
}
