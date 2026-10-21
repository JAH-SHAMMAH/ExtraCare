"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { useAuthStore } from "@/lib/store";
import { authApi, setAuth } from "@/lib/api";
import { lensForRole } from "@/lib/roleLens";
import type { MyContexts } from "@/hooks/useMyContexts";

/** Scope the session to one held role (server-enforced) and switch the dashboard
 *  to match. `null` = back to full access / the most privileged home. */
export function useSwitchRole(onDone?: () => void) {
  const user = useAuthStore((s) => s.user);
  const setUser = useAuthStore((s) => s.setUser);
  const setActiveRole = useAuthStore((s) => s.setActiveRole);
  const qc = useQueryClient();
  const router = useRouter();
  const [busy, setBusy] = useState<string | "all" | null>(null);

  const switchTo = async (roleId: string | null) => {
    const activeId = user?.active_role_id ?? null;
    if (activeId === roleId) { onDone?.(); return; }
    setBusy(roleId ?? "all");
    try {
      const roles = user?.roles ?? [];
      const data = await authApi.switchRole(roleId);
      setAuth(data.access_token, data.refresh_token);
      setUser(data.user);
      const cached = qc.getQueryData<MyContexts>(["me", "contexts"]);
      const slug = roleId ? roles.find((r) => r.id === roleId)?.slug : null;
      const lens = roleId
        ? lensForRole(slug, cached?.available_roles)
        : (cached?.default_role ?? lensForRole(roles[0]?.slug));
      qc.clear();
      if (lens) setActiveRole(lens);
      const label = roleId ? (roles.find((r) => r.id === roleId)?.name ?? "role") : "All roles";
      toast.success(roleId ? `Now acting as ${label}` : "Back to full access");
      onDone?.();
      router.push("/dashboard");
      router.refresh();
    } catch (e: any) {
      const detail = e?.response?.data?.detail;
      const status = e?.response?.status;
      toast.error(detail || (status ? `Couldn't switch role (HTTP ${status}).` : "Couldn't switch role."));
    } finally {
      setBusy(null);
    }
  };

  return { switchTo, busy };
}
