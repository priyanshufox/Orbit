/**
 * Orbit UI kit (layer 3 of the design tokens in app/globals.css).
 * Sticker look: ink borders, hard offset shadows, small radius, cream base, one brand colour
 * per screen, mustard for highlights.
 */
import type { ComponentProps, ReactNode } from "react";

/** Centered single-column page, phone-first. `tone="brand"` = green grid, for onboarding. */
export function Screen({
  children,
  tone = "default",
}: {
  children: ReactNode;
  tone?: "default" | "brand";
}) {
  const page = (
    <main className="mx-auto flex w-full max-w-md flex-1 flex-col justify-center gap-6 px-5 py-10">
      {children}
    </main>
  );
  if (tone === "default") return page;
  return <div className="bg-grid grain flex flex-1 flex-col">{page}</div>;
}

/** A cream panel that sits on a brand background (keeps body text off the green). */
export function Panel({ children, className = "" }: { children: ReactNode; className?: string }) {
  return (
    <div className={`sticker bg-background text-foreground space-y-5 p-5 ${className}`}>
      {children}
    </div>
  );
}

export function Heading({
  title,
  lead,
  display = false,
  tag,
}: {
  title: string;
  lead?: ReactNode;
  /** Hand-lettered display font: short hero titles only. */
  display?: boolean;
  /** Small italic-serif editorial tag above the title. */
  tag?: string;
}) {
  return (
    <header className="space-y-2">
      {tag && <p className="font-accent text-foreground/70 text-sm italic">{tag}</p>}
      <h1
        className={
          display
            ? "font-display text-5xl leading-none tracking-wide uppercase"
            : "font-heading text-3xl leading-tight font-extrabold tracking-tight"
        }
      >
        {title}
      </h1>
      {lead && <p className="text-foreground/75 text-base">{lead}</p>}
    </header>
  );
}

const buttonStyles = {
  primary: "sticker-sm press bg-action text-cream-100 hover:brightness-110",
  brand: "sticker-sm press bg-action-2 text-cream-100 hover:brightness-110",
  secondary:
    "border-ink bg-surface text-foreground rounded-[8px] border-[2.5px] hover:bg-highlight hover:text-on-highlight",
  ghost:
    "font-sans normal-case tracking-normal text-foreground/75 underline-offset-4 hover:text-foreground hover:underline",
} as const;

/** Caption-style button: ALL CAPS heavy sans, ink border, hard shadow, presses in. */
export function Button({
  variant = "primary",
  className = "",
  ...props
}: ComponentProps<"button"> & { variant?: keyof typeof buttonStyles }) {
  return (
    <button
      className={`font-heading inline-flex min-h-12 w-full items-center justify-center gap-2 px-5 py-2 text-sm font-extrabold tracking-wider uppercase focus-visible:outline-3 focus-visible:outline-offset-3 focus-visible:outline-sky-400 disabled:cursor-not-allowed disabled:opacity-50 ${buttonStyles[variant]} ${className}`}
      {...props}
    />
  );
}

export function Field({
  label,
  hint,
  className = "",
  ...input
}: ComponentProps<"input"> & { label: string; hint?: string }) {
  return (
    <label className="block space-y-1.5">
      <span className="font-heading text-xs font-extrabold tracking-wider uppercase">{label}</span>
      <input
        className={`border-ink bg-surface placeholder:text-foreground/40 focus:ring-highlight block h-12 w-full rounded-[8px] border-[2.5px] px-4 text-base transition-shadow outline-none focus:ring-4 ${className}`}
        {...input}
      />
      {hint && <span className="text-foreground/70 block text-xs">{hint}</span>}
    </label>
  );
}

/** Errors carry a symbol and words, never colour alone. */
export function ErrorText({ children }: { children?: ReactNode }) {
  if (!children) return null;
  return (
    <p
      role="alert"
      className="border-danger bg-surface flex items-start gap-2 rounded-[8px] border-[2.5px] px-3 py-2 text-sm"
    >
      <span aria-hidden className="text-danger font-heading font-extrabold">
        !
      </span>
      <span>{children}</span>
    </p>
  );
}

/** Speech-label tag: tooltips, coach marks, card labels. */
export function Tag({
  children,
  tone = "highlight",
}: {
  children: ReactNode;
  tone?: "highlight" | "surface";
}) {
  return (
    <span
      className={`font-heading border-ink inline-flex w-fit items-center rounded-full border-2 px-2.5 py-0.5 text-[11px] font-extrabold tracking-wider uppercase ${tone === "highlight" ? "bg-highlight text-on-highlight" : "bg-surface"}`}
    >
      {children}
    </span>
  );
}

/** The "webcam" content card: white surface, ink border, hard shadow, header bar with a
 * status dot, a pill tag and an optional close icon. */
export function Card({
  label,
  status = "live",
  onClose,
  children,
  className = "",
}: {
  label: ReactNode;
  status?: "live" | "idle" | "done";
  onClose?: () => void;
  children: ReactNode;
  className?: string;
}) {
  const dot = { live: "bg-tomato-500", idle: "bg-foreground/30", done: "bg-grid-green-500" }[
    status
  ];
  return (
    <section className={`sticker bg-surface animate-pop overflow-hidden ${className}`}>
      <header className="border-ink flex items-center gap-2 border-b-[2.5px] px-3 py-2">
        <span aria-hidden className={`border-ink h-2.5 w-2.5 rounded-full border-2 ${dot}`} />
        <Tag tone="surface">{label}</Tag>
        <span className="flex-1" />
        {onClose && (
          <button
            onClick={onClose}
            aria-label="Close"
            className="font-heading hover:bg-highlight hover:text-on-highlight grid h-7 w-7 place-items-center rounded-[6px] text-lg leading-none"
          >
            ×
          </button>
        )}
      </header>
      <div className="p-4">{children}</div>
    </section>
  );
}

/** Starburst badge for "New", top match, streaks; peeks from a card corner. */
export function Starburst({
  children,
  className = "",
}: {
  children: ReactNode;
  className?: string;
}) {
  const points = Array.from({ length: 24 }, (_, i) => {
    const r = i % 2 ? 36 : 50;
    const a = (Math.PI * i) / 12;
    return `${50 + r * Math.cos(a)},${50 + r * Math.sin(a)}`;
  }).join(" ");
  return (
    <span
      className={`animate-pop inline-grid h-16 w-16 place-items-center ${className.includes("absolute") ? "" : "relative"} ${className}`}
    >
      <svg viewBox="0 0 100 100" className="absolute inset-0 h-full w-full" aria-hidden>
        <polygon
          points={points}
          fill="var(--color-mustard-400)"
          stroke="var(--color-ink-900)"
          strokeWidth="4"
        />
      </svg>
      <span className="font-display text-ink-900 relative rotate-[-8deg] text-sm leading-none uppercase">
        {children}
      </span>
    </span>
  );
}

/** Sparkles: success and completion states only. */
export function Sparkles({ className = "" }: { className?: string }) {
  const star = "M12 0 L14.5 9.5 L24 12 L14.5 14.5 L12 24 L9.5 14.5 L0 12 L9.5 9.5 Z";
  return (
    <span aria-hidden className={`pointer-events-none inline-flex gap-1 ${className}`}>
      {[0, 300, 600].map((delay, i) => (
        <svg
          key={delay}
          viewBox="0 0 24 24"
          className="animate-sparkle h-5 w-5"
          style={{ animationDelay: `${delay}ms`, width: 14 + i * 4 }}
        >
          <path
            d={star}
            fill="var(--color-mustard-400)"
            stroke="var(--color-ink-900)"
            strokeWidth="1.5"
          />
        </svg>
      ))}
    </span>
  );
}

/** Hand-drawn marker circle that draws on around a selected item. */
export function MarkerCircle() {
  return (
    <svg
      aria-hidden
      viewBox="0 0 120 50"
      preserveAspectRatio="none"
      className="pointer-events-none absolute -inset-x-2 -inset-y-1.5 h-[calc(100%+12px)] w-[calc(100%+16px)]"
    >
      <path
        d="M8 26 C 6 8, 108 2, 114 20 C 120 40, 20 50, 9 34 C 4 26, 20 12, 40 10"
        fill="none"
        stroke="var(--color-tomato-700)"
        strokeWidth="3"
        strokeLinecap="round"
        pathLength={1}
        strokeDasharray={1}
        strokeDashoffset={1}
        className="animate-draw"
      />
    </svg>
  );
}

export function Loading() {
  return (
    <Screen>
      <div className="border-ink border-t-highlight h-10 w-10 animate-spin self-center rounded-full border-4" />
    </Screen>
  );
}
