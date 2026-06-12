"use client";

import { useEffect, useState } from "react";

/**
 * Returns `true` only once `flag` has been continuously `true` for at least
 * `delay` ms. When `flag` flips back to `false` we reset immediately.
 *
 * Use it to gate loading UI so fast requests (<300ms) never flash a spinner
 * or skeleton — the single biggest source of "twitchy" feel in SaaS dashboards.
 *
 *   const isLoading = query.isLoading;
 *   const showSkeleton = useDelayedFlag(isLoading);   // 300ms default
 */
export function useDelayedFlag(flag: boolean, delay = 300): boolean {
  const [show, setShow] = useState(false);

  useEffect(() => {
    if (!flag) {
      setShow(false);
      return;
    }
    const t = setTimeout(() => setShow(true), delay);
    return () => clearTimeout(t);
  }, [flag, delay]);

  return show;
}
