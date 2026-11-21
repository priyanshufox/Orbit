"use server";

import { headers } from "next/headers";
import { redirect } from "next/navigation";

import { serverApi } from "@/lib/api/server";
import type { components } from "@/lib/api/types";
import { auth } from "@/lib/auth";
import { safeNext, withNext } from "@/lib/onboarding";

/** `values` echoes what was submitted, so a form can refill itself after an error (React resets
 * forms once an action finishes). */
export type FormState =
  { error?: string; saved?: boolean; values?: Record<string, string> } | undefined;

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

type Hobby = components["schemas"]["SignUp"]["hobbies"] extends (infer H)[] | undefined ? H : never;

export async function signUp(_: FormState, form: FormData): Promise<FormState> {
  const name = String(form.get("name") ?? "").trim();
  const dateOfBirth = String(form.get("date_of_birth") ?? "");
  const hobbies = form.getAll("hobbies").map(String) as Hobby[];
  const values = { ...submitted(form), hobbies: hobbies.join(",") };
  if (!name) return { error: "Add the name your friends know you by.", values };
  if (!dateOfBirth) return { error: "Enter your date of birth.", values };

  const api = await apiOrSignIn();
  const { response } = await api.POST("/me/profile", {
    body: { name, date_of_birth: dateOfBirth, hobbies },
  });
  if (response.status === 403) {
    // Under 18: the API already deleted this sign-in; clear the now-orphaned cookie too.
    await auth.api.signOut({ headers: await headers() }).catch(() => undefined);
    redirect("/signup/not-eligible");
  }
  if (response.status === 422) {
    return { error: "Check your name, date of birth and hobbies (up to 6).", values };
  }
  if (!response.ok) return { error: "Something went wrong. Try again.", values };
  redirect(withNext("/consent", safeNext(form.get("next"))));
}

export async function updateProfile(_: FormState, form: FormData): Promise<FormState> {
  const name = String(form.get("name") ?? "").trim();
  const hobbies = form.getAll("hobbies").map(String) as Hobby[];
  const values = { ...submitted(form), hobbies: hobbies.join(",") };
  if (!name) return { error: "Add the name your friends know you by.", values };
  const api = await apiOrSignIn();
  const { response } = await api.PATCH("/me", { body: { name, hobbies } });
  if (!response.ok) return { error: "Couldn't save. Try again.", values };
  return { saved: true, values };
}

export async function giveConsent(form: FormData): Promise<void> {
  const api = await apiOrSignIn();
  const { response } = await api.POST("/me/consent");
  if (!response.ok) throw new Error(`Consent failed (${response.status})`);
  redirect(withNext("/roots?welcome=1", safeNext(form.get("next"))));
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
  redirect(safeNext(form.get("next")) ?? "/");
}

export async function signOut(): Promise<void> {
  await auth.api.signOut({ headers: await headers() });
  redirect("/signin");
}

export async function createRoom(): Promise<void> {
  const api = await apiOrSignIn();
  const { data, response } = await api.POST("/rooms");
  if (!data)
    throw new Error(
      response.status === 429 ? "Room limit reached for today" : "Couldn't create a room",
    );
  redirect(`/host/${data.code}`);
}

export async function goToRoom(_: FormState, form: FormData): Promise<FormState> {
  const code = String(form.get("code") ?? "")
    .trim()
    .toUpperCase()
    .replace(/0/g, "O")
    .replace(/1/g, "I");
  if (!/^[A-Z2-9]{6}$/.test(code)) return { error: "Room codes are 6 letters and numbers." };
  redirect(`/play/${code}`);
}

export async function deleteAccount(): Promise<void> {
  const api = await apiOrSignIn();
  const { response } = await api.DELETE("/me");
  if (!response.ok) throw new Error(`Delete failed (${response.status})`);
  await auth.api.signOut({ headers: await headers() }).catch(() => undefined);
  redirect("/signin?deleted=1");
}
