import { Heading, Screen } from "@/components/ui";

export default function NotEligiblePage() {
  return (
    <Screen>
      <Heading
        title="Orbit is for adults"
        lead="You need to be 18 or older to play. We didn't keep any of your details, and you've been signed out."
      />
    </Screen>
  );
}
