"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { UserCog, ChevronDown, Check, Loader2 } from "lucide-react";
import { cn } from "@/lib/utils";
import { useAuthStore } from "@/lib/store";
import { authApi, setAuth } from "@/lib/api";

// Match the sidebar-footer row styling (dark theme).
const ROW = "flex items-center gap-3 px-3 py-1 rounded-md text-sm font-semibold transition-colors w-full text-left";
const IDLE = "text-green-50/75 hover:bg-white/5 hover:text-white";

/**
 * "My Roles" — a GENUINE active-role switch in the account area. Distinct from
 * the TopBar "View as" persona lens: this scopes the session's actual RBAC
 * permissions to one held role (server-enforced via /auth/switch-role), or back
 * to full access ("All roles"). Rendered ONLY for users who hold 2+ roles.
 */
export function MyRolesMenu() {
  const user = useAuthStore((s) => s.user);
  const setUser = useAuthStore((s) => s.setUser);
  const qc = useQueryClient();
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState<string | "all" | null>(null);

  const roles = user?.roles ?? [];
  if (roles.length < 2) return null;              // nothing to switch → no clutter

  const activeId = user?.active_role_id ?? null;  // null = full access ("All roles")

  const handleSwitch = async (roleId: string | null) => {
    if ((activeId ?? null) === roleId) { setOpen(false); return; }
    setBusy(roleId ?? "all");
    try {
      const data = await authApi.switchRole(roleId);
      setAuth(data.access_token, data.refresh_token);
      setUser(data.user);
      // Permissions changed → drop cached data so everything refetches scoped,
      // and land on the always-accessible home so a now-forbidden route can't strand us.
      qc.clear();
      const label = roleId ? (roles.find((r) => r.id === roleId)?.name ?? "role") : "All roles";
      toast.success(roleId ? `Now acting as ${label}` : "Back to full access");
      setOpen(false);
      router.push("/dashboard");
      router.refresh();
    } catch {
      toast.error("Couldn't switch role.");
    } finally {
      setBusy(null);
    }
  };

  const activeLabel = activeId ? (roles.find((r) => r.id === activeId)?.name ?? "…") : "All roles";

  return (
    <div>
      <button onClick={() => setOpen((o) => !o)} className={cn(ROW, IDLE)} aria-expanded={open}>
        <UserCog size={18} strokeWidth={1.75} className="shrink-0" />
        <span className="truncate flex-1">My Roles</span>
        <span className="text-[10px] text-green-200/60 truncate max-w-[80px]">{activeLabel}</span>
        <ChevronDown size={14} className={cn("shrink-0 transition-transform", open && "rotate-180")} />
      </button>

      {open && (
        <div className="mt-0.5 ml-2 pl-3 border-l border-white/10 space-y-0.5 py-0.5">
          <RoleRow label="All roles" hint="Full access" active={activeId === null}
                   busy={busy === "all"} onClick={() => handleSwitch(null)} />
          {roles.map((r) => (
            <RoleRow key={r.id} label={r.name} active={activeId === r.id}
                     busy={busy === r.id} onClick={() => handleSwitch(r.id)} />
          ))}
        </div>
      )}
    </div>
  );
}

function RoleRow({ label, hint, active, busy, onClick }: {
  label: string; hint?: string; active: boolean; busy: boolean; onClick: () => void;
}) {
  return (
    <button
      onClick={onClick}
      disabled={busy}
      className={cn(
        "flex items-center gap-2 px-2.5 py-1.5 rounded-md text-xs w-full text-left transition-colors",
        active ? "bg-white/10 text-white font-semibold" : "text-green-50/70 hover:bg-white/5 hover:text-white",
      )}
    >
      <span className="flex-1 truncate">
        {label}
        {hint && <span className="ml-1.5 text-[10px] text-green-200/40">{hint}</span>}
      </span>
      {busy ? <Loader2 size={13} className="animate-spin shrink-0" />
            : active ? <Check size={13} className="text-white shrink-0" /> : null}
    </button>
  );
}
