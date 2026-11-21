"use client";

import { useEffect, useState } from "react";

export type ThemePref = "system" | "light" | "dark";
const KEY = "orbit-theme";
const ORDER: ThemePref[] = ["system", "light", "dark"];
const LABEL: Record<ThemePref, string> = { system: "Auto", light: "Light", dark: "Dark" };
const ICON: Record<ThemePref, string> = { system: "◐", light: "☀", dark: "☾" };

/** Runs in <head> before first paint, so there's no flash of the wrong theme. */
export const themeBootScript = `(function(){try{var p=localStorage.getItem("${KEY}")||"system";var d=p==="dark"||(p==="system"&&matchMedia("(prefers-color-scheme: dark)").matches);document.documentElement.dataset.theme=d?"dark":"light";document.documentElement.dataset.themePref=p}catch(e){document.documentElement.dataset.theme="light"}})()`;

function apply(pref: ThemePref) {
  const dark =
    pref === "dark" || (pref === "system" && matchMedia("(prefers-color-scheme: dark)").matches);
  document.documentElement.dataset.theme = dark ? "dark" : "light";
  document.documentElement.dataset.themePref = pref;
}

export function ThemeToggle() {
  const [pref, setPref] = useState<ThemePref>("system");

  useEffect(() => {
    const saved = (document.documentElement.dataset.themePref as ThemePref) || "system";
    // Sync with what the boot script already applied (no setState during render).
    const t = setTimeout(() => setPref(saved), 0);
    const media = matchMedia("(prefers-color-scheme: dark)");
    const onChange = () => {
      if ((document.documentElement.dataset.themePref ?? "system") === "system") apply("system");
    };
    media.addEventListener("change", onChange);
    return () => {
      clearTimeout(t);
      media.removeEventListener("change", onChange);
    };
  }, []);

  function choose(next: ThemePref) {
    setPref(next);
    apply(next);
    try {
      localStorage.setItem(KEY, next);
    } catch {
      // private mode: the choice still applies to this visit
    }
  }

  return (
    <div
      role="radiogroup"
      aria-label="Theme"
      className="border-ink bg-surface fixed top-3 right-3 z-50 inline-flex rounded-full border-2 p-0.5"
    >
      {ORDER.map((p) => {
        const on = p === pref;
        return (
          <button
            key={p}
            role="radio"
            aria-checked={on}
            aria-label={LABEL[p]}
            title={LABEL[p]}
            onClick={() => choose(p)}
            className={`grid h-7 w-7 place-items-center rounded-full text-sm transition-colors ${
              on ? "bg-foreground text-background" : "text-foreground/70 hover:text-foreground"
            }`}
          >
            <span aria-hidden>{ICON[p]}</span>
          </button>
        );
      })}
    </div>
  );
}
