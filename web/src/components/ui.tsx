import type { ComponentProps, ReactNode } from "react";

/** Centered single-column page, phone-first. */
export function Screen({ children }: { children: ReactNode }) {
  return (
    <main className="mx-auto flex w-full max-w-md flex-1 flex-col justify-center gap-6 px-5 py-10">
      {children}
    </main>
  );
}

export function Heading({ title, lead }: { title: string; lead?: ReactNode }) {
  return (
    <header className="space-y-2">
      <h1 className="text-3xl font-semibold tracking-tight">{title}</h1>
      {lead && <p className="text-foreground/70 text-base">{lead}</p>}
    </header>
  );
}

const buttonStyles = {
  primary: "bg-violet-600 text-white hover:bg-violet-500 disabled:bg-violet-600/50",
  secondary: "border border-foreground/15 bg-transparent hover:bg-foreground/5 disabled:opacity-50",
  ghost:
    "bg-transparent text-foreground/70 hover:text-foreground underline-offset-4 hover:underline",
} as const;

export function Button({
  variant = "primary",
  className = "",
  ...props
}: ComponentProps<"button"> & { variant?: keyof typeof buttonStyles }) {
  return (
    <button
      className={`inline-flex h-12 w-full items-center justify-center gap-2 rounded-xl px-5 text-base font-medium transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-violet-500 ${buttonStyles[variant]} ${className}`}
      {...props}
    />
  );
}

export function Field({
  label,
  hint,
  ...input
}: ComponentProps<"input"> & { label: string; hint?: string }) {
  return (
    <label className="block space-y-1.5">
      <span className="text-sm font-medium">{label}</span>
      <input
        className="border-foreground/15 bg-background placeholder:text-foreground/40 block h-12 w-full rounded-xl border px-4 text-base outline-none focus:border-violet-500 focus:ring-2 focus:ring-violet-500/30"
        {...input}
      />
      {hint && <span className="text-foreground/60 block text-xs">{hint}</span>}
    </label>
  );
}

export function ErrorText({ children }: { children?: ReactNode }) {
  if (!children) return null;
  return (
    <p
      role="alert"
      className="rounded-lg bg-red-500/10 px-3 py-2 text-sm text-red-700 dark:text-red-300"
    >
      {children}
    </p>
  );
}

export function Loading() {
  return (
    <Screen>
      <div className="h-8 w-8 animate-spin self-center rounded-full border-2 border-violet-500 border-t-transparent" />
    </Screen>
  );
}
