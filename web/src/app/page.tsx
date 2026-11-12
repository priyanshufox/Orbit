import Link from "next/link";
import { Suspense } from "react";

import { Button, Heading, Loading, Screen } from "@/components/ui";
import { signOut } from "@/lib/actions";
import { requireStage } from "@/lib/onboarding";

export default function Home() {
  return (
    <Suspense fallback={<Loading />}>
      <HomeScreen />
    </Suspense>
  );
}

async function HomeScreen() {
  // Visitors who aren't signed in, or are mid-onboarding, are sent to their next step.
  const { me } = await requireStage("ready");
  return (
    <Screen>
      <Heading title={`Hi ${me.name}`} lead="See who's in your orbit." />
      <p className="bg-foreground/5 text-foreground/70 rounded-2xl p-4 text-sm">
        Creating and joining rooms arrives in Phase 3.
      </p>
      <div className="space-y-2">
        <Link
          href="/roots"
          className="border-foreground/15 hover:bg-foreground/5 block rounded-xl border px-5 py-3 text-center"
        >
          Edit your roots
        </Link>
        <form action={signOut}>
          <Button variant="ghost" type="submit">
            Sign out
          </Button>
        </form>
      </div>
    </Screen>
  );
}
