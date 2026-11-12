"use client";

import Link from "next/link";
import { useActionState } from "react";

import { Button, ErrorText, Field } from "@/components/ui";
import { type FormState, saveRoots } from "@/lib/actions";
import type { Roots } from "@/lib/api/server";

export function RootsForm({ roots }: { roots: Roots }) {
  const [state, action, pending] = useActionState<FormState, FormData>(saveRoots, undefined);
  const childhood = roots.childhood_cities ?? [];
  // After a failed save, show what was typed rather than what is stored.
  const value = (name: string, stored: string | null | undefined) =>
    state?.values?.[name] ?? stored ?? "";

  return (
    <form action={action} className="space-y-5">
      <Field
        label="Birth city"
        name="birth_city"
        defaultValue={value("birth_city", roots.birth_city)}
        placeholder="Mumbai"
      />

      <fieldset className="space-y-3">
        <legend className="text-sm font-medium">School</legend>
        <Field
          label="Name"
          name="school_name"
          defaultValue={value("school_name", roots.school?.name)}
          placeholder="Green Valley School"
        />
        <Field
          label="City"
          name="school_city"
          defaultValue={value("school_city", roots.school?.city)}
          placeholder="Noida"
        />
      </fieldset>

      <fieldset className="space-y-3">
        <legend className="text-sm font-medium">Cities you grew up in (up to 3)</legend>
        {[0, 1, 2].map((i) => (
          <Field
            key={i}
            label={`City ${i + 1}`}
            name={`childhood_${i + 1}`}
            defaultValue={value(`childhood_${i + 1}`, childhood[i])}
          />
        ))}
      </fieldset>

      <ErrorText>{state?.error}</ErrorText>
      <Button type="submit" disabled={pending}>
        {pending ? "Saving…" : "Save"}
      </Button>
      <Link href="/" className="text-foreground/70 block text-center text-sm hover:underline">
        Skip for now
      </Link>
    </form>
  );
}
