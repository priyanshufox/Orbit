import { Suspense } from "react";

import { Heading, Loading, Panel, Screen } from "@/components/ui";
import { requireStage, safeNext } from "@/lib/onboarding";

import { SignUpForm } from "./sign-up-form";

export default function SignUpPage(props: PageProps<"/signup">) {
  return (
    <Suspense fallback={<Loading />}>
      <SignUp searchParams={props.searchParams} />
    </Suspense>
  );
}

async function SignUp({ searchParams }: { searchParams: PageProps<"/signup">["searchParams"] }) {
  const next = safeNext((await searchParams).next);
  const { me } = await requireStage("age", next);
  return (
    <Screen tone="brand">
      <Panel>
        <Heading title="Create your profile" lead="Three quick things, then you're in." />
        <SignUpForm name={me.name} next={next} />
      </Panel>
    </Screen>
  );
}
