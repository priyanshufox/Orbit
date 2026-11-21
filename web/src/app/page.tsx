import Link from "next/link";
import { Suspense } from "react";

import { DeleteAccount } from "@/components/home/delete-account";
import { JoinForm } from "@/components/home/join-form";
import { Button, Heading, Loading, Screen } from "@/components/ui";
import { createRoom, signOut } from "@/lib/actions";
import { requireStage } from "@/lib/onboarding";

export default function Home() {
  return (
    <Suspense fallback={<Loading />}>
      <HomeScreen />
    </Suspense>
  );
}

async function HomeScreen() {
  // Visitors who aren't signed in, or are mid-sign-up, are sent to their next step.
  const { me } = await requireStage("ready");
  return (
    <Screen>
      <Heading display title={`Hi ${me.name.split(" ")[0]}`} lead="See who's in your orbit." />

      <form action={createRoom}>
        <Button type="submit">Host a room</Button>
      </form>

      <JoinForm />

      <nav className="flex flex-wrap items-center justify-between gap-x-4 gap-y-2 pt-2 text-sm">
        <Link href="/history" className="font-semibold underline underline-offset-4">
          Past orbits
        </Link>
        <Link href="/profile" className="font-semibold underline underline-offset-4">
          Your profile
        </Link>
        <form action={signOut}>
          <button type="submit" className="text-foreground/75 underline underline-offset-4">
            Sign out
          </button>
        </form>
      </nav>
      <div className="border-foreground/15 border-t pt-4">
        <DeleteAccount />
      </div>
    </Screen>
  );
}
