import Link from "next/link";
import { Suspense } from "react";

import { Heading, Loading, Screen } from "@/components/ui";
import { requireStage } from "@/lib/onboarding";

import { ProfileForm } from "./profile-form";

export default function ProfilePage() {
  return (
    <Suspense fallback={<Loading />}>
      <Profile />
    </Suspense>
  );
}

async function Profile() {
  const { me } = await requireStage("ready");
  return (
    <Screen>
      <Heading title="Your profile" />
      <ProfileForm name={me.name} hobbies={me.hobbies} />
      <div className="flex justify-between text-sm">
        <Link href="/roots" className="font-semibold underline underline-offset-4">
          Edit your roots
        </Link>
        <Link href="/" className="font-semibold underline underline-offset-4">
          Home
        </Link>
      </div>
    </Screen>
  );
}
