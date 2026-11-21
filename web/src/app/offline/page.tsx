import { Heading, Screen } from "@/components/ui";

export default function OfflinePage() {
  return (
    <Screen>
      <Heading
        title="You're offline"
        lead="Orbit needs a connection to play. Your answers are saved on this phone and sent as soon as you're back online."
      />
    </Screen>
  );
}
