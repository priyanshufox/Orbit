"use client";

import { useActionState } from "react";

import { HobbyPicker } from "@/components/profile/hobby-picker";
import { Button, ErrorText, Field } from "@/components/ui";
import { signUp } from "@/lib/actions";

export function SignUpForm({ name, next }: { name: string; next: string | null }) {
  const [state, action, pending] = useActionState(signUp, undefined);
  const hobbies = state?.values?.hobbies?.split(",").filter(Boolean) ?? [];
  return (
    <form action={action} className="space-y-5">
      {next && <input type="hidden" name="next" value={next} />}
      <Field
        label="Your name"
        name="name"
        required
        maxLength={40}
        autoComplete="nickname"
        defaultValue={state?.values?.name ?? name}
        hint="How friends will see you in rooms."
      />
      <Field
        label="Date of birth"
        name="date_of_birth"
        type="date"
        required
        defaultValue={state?.values?.date_of_birth}
        max={new Date().toISOString().slice(0, 10)}
        hint="Orbit is for 18+. Only the year is saved."
      />
      <HobbyPicker key={hobbies.join(",")} initial={hobbies} />
      <ErrorText>{state?.error}</ErrorText>
      <Button type="submit" disabled={pending}>
        {pending ? "Creating…" : "Create my profile"}
      </Button>
    </form>
  );
}
