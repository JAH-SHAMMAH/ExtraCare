"use client";

import { doneProgress, startProgress } from "./progress";

/**
 * Lightweight nav-timing instrumentation.
 *
 * Goal: let us answer "how fast did this menu click feel?" with a number,
 * not vibes. We can't plumb this through the Next.js router internals, so
 * we bracket it with two marks:
 *
 *   markNavClick(href)  // fires on sidebar / menu click
 *   markNavPainted(path) // fires after the destination page renders
 *
 * The measure is logged to the console and written to performance.measure
 * so it also shows up in DevTools > Performance. Toggle on via
 * localStorage.setItem("ec:perf", "1") to avoid console noise in day-to-day
 * use — the instrumentation is a tool, not a default.
 */

const PENDING_KEY = "__ec_nav_pending__";

function enabled(): boolean {
  if (typeof window === "undefined") return false;
  try {
    return window.localStorage.getItem("ec:perf") === "1";
  } catch {
    return false;
  }
}

type Pending = { href: string; t0: number };

function getPending(): Pending | null {
  if (typeof window === "undefined") return null;
  return (window as any)[PENDING_KEY] ?? null;
}

function setPending(p: Pending | null): void {
  if (typeof window === "undefined") return;
  (window as any)[PENDING_KEY] = p;
}

export function markNavClick(href: string): void {
  // Progress bar is always on — it's a user-facing signal, not dev-only
  // instrumentation. Keep it outside the `enabled()` gate.
  startProgress();
  if (!enabled()) return;
  const t0 = performance.now();
  setPending({ href, t0 });
  try {
    performance.mark(`nav:click:${href}`);
  } catch {
    // ignore — older browsers without User Timing L3
  }
}

export function markNavPainted(path: string): void {
  // Always close out the progress bar on paint — regardless of whether dev
  // timing is enabled. Guards against a stuck bar if markNavClick was fired
  // but perf gating wasn't on.
  doneProgress();
  if (!enabled()) return;
  const pending = getPending();
  if (!pending) return;
  // Only measure if the painted path matches (or starts with) the click
  // target — otherwise we'd conflate back/forward with click nav.
  if (!path.startsWith(pending.href) && pending.href !== path) return;
  const elapsed = performance.now() - pending.t0;
  setPending(null);
  try {
    performance.mark(`nav:paint:${path}`);
    performance.measure(
      `nav ${pending.href} → paint`,
      `nav:click:${pending.href}`,
      `nav:paint:${path}`,
    );
  } catch {
    // ignore
  }
  // eslint-disable-next-line no-console
  console.log(`[nav] ${pending.href} → first paint: ${elapsed.toFixed(1)}ms`);
}
