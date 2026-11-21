import { Suspense } from "react";

import { Heading, Loading, Panel, Screen } from "@/components/ui";
import { googleEnabled } from "@/lib/auth";
import { requireStage, safeNext } from "@/lib/onboarding";

import { SignInForm } from "./sign-in-form";

export default function SignInPage(props: PageProps<"/signin">) {
  return (
    <Suspense fallback={<Loading />}>
      <SignIn searchParams={props.searchParams} />
    </Suspense>
  );
}

async function SignIn({ searchParams }: { searchParams: PageProps<"/signin">["searchParams"] }) {
  const params = await searchParams;
  const next = safeNext(params.next);
  await requireStage("signin", next); // signed-in visitors go to their next step
  const joining = next?.startsWith("/play/");

  return (
    <Screen tone="brand">
      <Panel>
        <Heading
          display
          title="Orbit"
          lead={
            joining
              ? "Sign in or create an account to join the room."
              : "Sign in, or create an account in a minute."
          }
        />
        {params.deleted && (
          <p className="border-ink bg-surface rounded-[8px] border-2 px-4 py-3 text-sm">
            ✓ Your account and everything in it has been deleted.
          </p>
        )}
        <SignInForm googleEnabled={googleEnabled} callbackURL={next ?? "/"} />
      </Panel>
    </Screen>
  );
}
