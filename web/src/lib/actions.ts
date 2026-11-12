"use server";

import { headers } from "next/headers";
import { redirect } from "next/navigation";

import { serverApi } from "@/lib/api/server";
import { auth } from "@/lib/auth";

/** `values` echoes what was submitted, so a form can refill itself after an error (React resets
 * forms once an action finishes). */
export type FormState = { error?: string; values?: Record<string, string> } | undefined;

function submitted(form: FormData): Record<string, string> {
  return Object.fromEntries(
    [...form.entries()].filter(([k, v]) => !k.startsWith("$") && typeof v === "string"),
  ) as Record<string, string>;
}

async function apiOrSignIn() {
  const api = await serverApi();
  if (!api) redirect("/signin");
  return api;
}

export async function submitAge(_: FormState, form: FormData): Promise<FormState> {
  const dateOfBirth = String(form.get("date_of_birth") ?? "");
  if (!dateOfBirth) return { error: "Enter your date of birth." };

  const api = await apiOrSignIn();
  const { response } = await api.POST("/me/age", { body: { date_of_birth: dateOfBirth } });
  if (response.status === 403) {
    // The API already deleted this sign-in; clear the now-orphaned cookie too.
    await auth.api.signOut({ headers: await headers() }).catch(() => undefined);
    redirect("/age/not-eligible");
  }
  if (response.status === 422) {
    return { error: "That date doesn't look right.", values: submitted(form) };
  }
  if (!response.ok) return { error: "Something went wrong. Try again.", values: submitted(form) };
  redirect("/consent");
}

export async function giveConsent(): Promise<void> {
  const api = await apiOrSignIn();
  const { response } = await api.POST("/me/consent");
  if (!response.ok) throw new Error(`Consent failed (${response.status})`);
  redirect("/roots?welcome=1");
}

export async function saveRoots(_: FormState, form: FormData): Promise<FormState> {
  const text = (name: string) => String(form.get(name) ?? "").trim();
  const schoolName = text("school_name");
  const schoolCity = text("school_city");
  if (Boolean(schoolName) !== Boolean(schoolCity)) {
    return {
      error: "Add both the school's name and its city, or leave both empty.",
      values: submitted(form),
    };
  }

  const api = await apiOrSignIn();
  const { response } = await api.PUT("/me/roots", {
    body: {
      birth_city: text("birth_city") || null,
      school: schoolName ? { name: schoolName, city: schoolCity } : null,
      childhood_cities: ["childhood_1", "childhood_2", "childhood_3"].map(text).filter(Boolean),
    },
  });
  if (!response.ok) {
    return { error: "Couldn't save. Check the fields and try again.", values: submitted(form) };
  }
  redirect("/");
}

export async function signOut(): Promise<void> {
  await auth.api.signOut({ headers: await headers() });
  redirect("/signin");
}
