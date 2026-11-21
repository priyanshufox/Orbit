"use client";

import { useActionState } from "react";

import { HobbyPicker } from "@/components/profile/hobby-picker";
import { Button, ErrorText, Field } from "@/components/ui";
import { updateProfile } from "@/lib/actions";

export function ProfileForm({ name, hobbies }: { name: string; hobbies: string[] }) {
  const [state, action, pending] = useActionState(updateProfile, undefined);
  const current = state?.values?.hobbies?.split(",").filter(Boolean) ?? hobbies;
  return (
    <form action={action} className="space-y-5">
      <Field
        label="Your name"
        name="name"
        required
        maxLength={40}
        defaultValue={state?.values?.name ?? name}
      />
      <HobbyPicker key={current.join(",")} initial={current} />
      <ErrorText>{state?.error}</ErrorText>
      {state?.saved && !state.error && <p className="text-sm font-semibold">✓ Saved</p>}
      <Button type="submit" disabled={pending}>
        {pending ? "Saving…" : "Save"}
      </Button>
    </form>
  );
}
