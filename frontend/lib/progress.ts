"use client";

/**
 * Global nav-progress bus.
 *
 * Any code that kicks off a route transition can call `startProgress()`; the
 * dashboard layout calls `doneProgress()` once the destination pathname
 * settles. The `<TopProgress />` component subscribes and renders.
 *
 * Two delays keep the bar from twitching:
 *   - 150ms appear delay: instant transitions never flash the bar.
 *   - 220ms linger: once shown, the bar stays visible for at least this long
 *     so the user perceives a completed animation.
 */

type Listener = (active: boolean, tick: number) => void;

const APPEAR_DELAY_MS = 150;
const MIN_VISIBLE_MS = 220;

let active = false;
let tick = 0;
let shownAt = 0;
let appearTimer: ReturnType<typeof setTimeout> | null = null;
let doneTimer: ReturnType<typeof setTimeout> | null = null;
const listeners = new Set<Listener>();

function emit(): void {
  for (const l of listeners) l(active, tick);
}

export function startProgress(): void {
  if (doneTimer) {
    clearTimeout(doneTimer);
    doneTimer = null;
  }
  // Already running — just bump the tick so subscribers can restart their
  // CSS animations (keyframes restart on remount keyed by `tick`).
  if (active) {
    tick++;
    shownAt = Date.now();
    emit();
    return;
  }
  if (appearTimer) return; // already waiting
  appearTimer = setTimeout(() => {
    appearTimer = null;
    active = true;
    tick++;
    shownAt = Date.now();
    emit();
  }, APPEAR_DELAY_MS);
}

export function doneProgress(): void {
  // Cancel a pending appear — the transition finished inside the delay.
  if (appearTimer) {
    clearTimeout(appearTimer);
    appearTimer = null;
    return;
  }
  if (!active) return;
  const heldFor = Date.now() - shownAt;
  const remaining = Math.max(0, MIN_VISIBLE_MS - heldFor);
  if (doneTimer) clearTimeout(doneTimer);
  doneTimer = setTimeout(() => {
    doneTimer = null;
    active = false;
    tick++;
    emit();
  }, remaining);
}

export function subscribeProgress(l: Listener): () => void {
  listeners.add(l);
  // Push the current state so subscribers hydrate in sync.
  l(active, tick);
  return () => {
    listeners.delete(l);
  };
}
