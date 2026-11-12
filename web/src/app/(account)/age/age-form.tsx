"use client";

import { useActionState } from "react";

import { Button, ErrorText, Field } from "@/components/ui";
import { submitAge } from "@/lib/actions";

export function AgeForm() {
  const [state, action, pending] = useActionState(submitAge, undefined);
  return (
    <form action={action} className="space-y-4">
      <Field
        label="Date of birth"
        name="date_of_birth"
        type="date"
        required
        defaultValue={state?.values?.date_of_birth}
        max={new Date().toISOString().slice(0, 10)}
        hint="Only the year is saved. Orbit is for people 18 and over."
      />
      <ErrorText>{state?.error}</ErrorText>
      <Button type="submit" disabled={pending}>
        {pending ? "Checking…" : "Continue"}
      </Button>
    </form>
  );
}
