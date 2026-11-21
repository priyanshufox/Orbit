import { Suspense } from "react";

import { Button, Heading, Loading, Panel, Screen } from "@/components/ui";
import { giveConsent } from "@/lib/actions";
import { requireStage, safeNext } from "@/lib/onboarding";

export default function ConsentPage(props: PageProps<"/consent">) {
  return (
    <Suspense fallback={<Loading />}>
      <Consent searchParams={props.searchParams} />
    </Suspense>
  );
}

// Draft notice for task 2.7. Must be reviewed by a lawyer before public launch (task 10.7).
const COLLECTED = [
  ["Your answers", "to the round's questions about habits and interests"],
  ["Your reactions", "to the shared cards (like, laugh, skip, send)"],
  ["Likes and follows", "you give other players in the room"],
  [
    "Your name and hobbies",
    'from your profile; shared hobbies appear on the graph, like "Both into Cricket"',
  ],
  [
    "Your roots, if you add them",
    'birth city, school, childhood cities. Never shown to others; a match only appears as "Shared roots"',
  ],
];

async function Consent({ searchParams }: { searchParams: PageProps<"/consent">["searchParams"] }) {
  const next = safeNext((await searchParams).next);
  await requireStage("consent", next);
  return (
    <Screen tone="brand">
      <Panel>
        <Heading
          title="Before you play"
          lead="Orbit scores how close you are to the people in your room."
        />

        <section className="space-y-3 text-sm">
          <p className="font-heading font-extrabold uppercase">What we collect in a room</p>
          <ul className="space-y-2">
            {COLLECTED.map(([what, detail]) => (
              <li key={what} className="sticker-sm bg-surface px-4 py-3">
                <strong>{what}</strong> <span className="text-foreground/75">{detail}</span>
              </li>
            ))}
          </ul>
          <p className="font-heading font-extrabold uppercase">Who sees it</p>
          <p className="text-foreground/75">
            Everyone in the room sees the closeness graph with every pair&apos;s score, on the host
            screen and on their phones.
          </p>
          <p className="font-heading font-extrabold uppercase">How long we keep it</p>
          <p className="text-foreground/75">
            Room data is deleted 48 hours after the room is created. Your account keeps your profile
            and a snapshot of your own graph. You can leave a room and delete your data at any time,
            and delete your account from your profile.
          </p>
        </section>

        <form action={giveConsent}>
          {next && <input type="hidden" name="next" value={next} />}
          <Button type="submit">I agree, continue</Button>
        </form>
      </Panel>
    </Screen>
  );
}
