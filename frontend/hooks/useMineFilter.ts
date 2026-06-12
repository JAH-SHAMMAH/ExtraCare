"use client";

import { useSearchParams, useRouter, usePathname } from "next/navigation";

/**
 * Reads the `?mine=1` flag used by "View mine" entry points and returns
 * a `{ mine, setMine }` pair. Persisted in the URL so a shared link keeps
 * the same scope. Admins can always clear it via the returned setter.
 */
export function useMineFilter() {
  const params = useSearchParams();
  const router = useRouter();
  const pathname = usePathname();

  const mine = params.get("mine") === "1";

  const setMine = (next: boolean) => {
    const q = new URLSearchParams(params.toString());
    if (next) q.set("mine", "1");
    else q.delete("mine");
    const qs = q.toString();
    router.replace(qs ? `${pathname}?${qs}` : pathname);
  };

  return { mine, setMine };
}
