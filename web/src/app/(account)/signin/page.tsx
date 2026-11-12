import { Suspense } from "react";

import { Heading, Loading, Screen } from "@/components/ui";
import { googleEnabled } from "@/lib/auth";
import { requireStage } from "@/lib/onboarding";

import { SignInForm } from "./sign-in-form";

const DEV_USERS = ["dev1", "dev2", "dev3", "dev4", "dev5"];

export default function SignInPage() {
  return (
    <Suspense fallback={<Loading />}>
      <SignIn />
    </Suspense>
  );
}

async function SignIn() {
  await requireStage("signin"); // signed-in visitors go to their next step
  const isDev = process.env.NODE_ENV !== "production";

  return (
    <Screen>
      <Heading title="Orbit" lead="See who's in your orbit. Sign in to join a room." />
      <SignInForm googleEnabled={googleEnabled} isDev={isDev} />
      {isDev && (
        <section className="space-y-2 rounded-2xl border border-dashed border-amber-500/50 p-4">
          <p className="text-xs font-medium tracking-wide text-amber-700 uppercase dark:text-amber-300">
            Dev login (not in production)
          </p>
          <div className="grid grid-cols-5 gap-2">
            {DEV_USERS.map((name) => (
              <a
                key={name}
                href={`/api/dev-login?email=${name}@orbit.test`}
                className="border-foreground/15 hover:bg-foreground/5 rounded-lg border py-2 text-center text-sm"
              >
                {name}
              </a>
            ))}
          </div>
        </section>
      )}
    </Screen>
  );
}
