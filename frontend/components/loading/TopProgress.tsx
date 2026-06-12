"use client";

import { useEffect, useState } from "react";
import { subscribeProgress } from "@/lib/progress";

/**
 * Top-of-page progress bar for route transitions. Subscribes to the global
 * progress bus; renders nothing when idle.
 *
 * Using `transform: scaleX()` (via tailwind keyframes) instead of `width` so
 * the browser can composite it — no layout work during the crawl.
 */
export function TopProgress() {
  const [active, setActive] = useState(false);
  const [tick, setTick] = useState(0);
  // "closing" = just finished; keeps the bar around for a 250ms slide-to-100 exit.
  const [closing, setClosing] = useState(false);

  useEffect(() => {
    return subscribeProgress((isActive, t) => {
      setTick(t);
      if (isActive) {
        setActive(true);
        setClosing(false);
      } else if (active) {
        // Transition from active → closing so we can animate out gracefully.
        setClosing(true);
        setActive(false);
        const timer = setTimeout(() => setClosing(false), 260);
        return () => clearTimeout(timer);
      }
    });
    // We want this subscription to bind once for the lifetime of the layout.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  if (!active && !closing) return null;

  return (
    <div
      className="fixed top-0 left-0 right-0 z-[100] h-[2px] pointer-events-none"
      aria-hidden
    >
      <div
        // `key={tick}` restarts the keyframes on each nav start.
        key={tick}
        className={
          active
            ? "h-full origin-left bg-gradient-to-r from-brand-500 via-brand-600 to-brand-500 shadow-[0_0_10px_rgba(0,87,194,0.45)] animate-nav-progress"
            : "h-full origin-left bg-gradient-to-r from-brand-500 via-brand-600 to-brand-500 shadow-[0_0_10px_rgba(0,87,194,0.45)] scale-x-100 opacity-0 transition-all duration-[260ms] ease-out"
        }
        style={active ? undefined : { transform: "scaleX(1)" }}
      />
    </div>
  );
}
