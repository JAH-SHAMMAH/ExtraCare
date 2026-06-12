"use client";

import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { searchApi } from "@/lib/api";

/** Returns `value` after it stops changing for `delay` ms. */
function useDebouncedValue<T>(value: T, delay = 250): T {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const t = setTimeout(() => setDebounced(value), delay);
    return () => clearTimeout(t);
  }, [value, delay]);
  return debounced;
}

export function useGlobalSearch(query: string, modules?: string[]) {
  // Fire one request per settled query — not one per keystroke. 250ms is
  // the sweet spot where fast typists don't burn the backend but the UI
  // still feels live.
  const debounced = useDebouncedValue(query.trim(), 250);
  return useQuery({
    queryKey: ["global-search", debounced, modules],
    queryFn: () => searchApi.global(debounced, modules),
    enabled: debounced.length >= 2,
    staleTime: 30_000,
  });
}
