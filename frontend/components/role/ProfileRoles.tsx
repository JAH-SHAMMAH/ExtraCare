"use client";

import { Check, Loader2, UserCog } from "lucide-react";
import { cn } from "@/lib/utils";
import { useAuthStore } from "@/lib/store";
import { useSwitchRole } from "@/hooks/useSwitchRole";

/** Profile → "My Roles": lists every role the user holds. With 2+ roles each one
 *  is selectable and the dashboard switches to that role's home. */
export function ProfileRoles() {
  const user = useAuthStore((s) => s.user);
  const { switchTo, busy } = useSwitchRole();
  const roles = user?.roles ?? [];
  if (!user) return null;
  const activeId = user.active_role_id ?? null;
  const multi = roles.length > 1;

  const Row = ({ id, label, hint }: { id: string | null; label: string; hint?: string }) => {
    const active = activeId === id;
    const loading = busy === (id ?? "all");
    return (
      <button
        type="button"
        onClick={() => switchTo(id)}
        disabled={!!busy}
        className={cn(
          "flex items-center gap-3 w-full text-left px-3 py-2.5 rounded-lg border text-sm transition-colors",
          active ? "border-brand-300 bg-brand-50 text-brand-700 font-semibold" : "border-slate-200 hover:bg-slate-50 text-slate-700",
        )}
      >
        <span className="flex-1 min-w-0 truncate">{label}{hint && <span className="ml-2 text-xs font-normal text-slate-400">{hint}</span>}</span>
        {loading ? <Loader2 size={15} className="animate-spin" /> : active ? <Check size={15} /> : null}
      </button>
    );
  };

  return (
    <div className="bg-white rounded-xl border border-slate-200 p-6">
      <h3 className="text-sm font-bold text-slate-800 mb-1 flex items-center gap-2"><UserCog size={15} /> My Roles</h3>
      <p className="text-xs text-slate-400 mb-4">
        {multi ? "You hold more than one role. Pick one and your dashboard and menu switch to it." : "The role assigned to you."}
      </p>
      <div className="space-y-2">
        {multi && <Row id={null} label="All roles" hint="Full access" />}
        {roles.length === 0 && (
          <p className="text-sm text-slate-600 capitalize">{user.primary_role?.replace("_", " ")}</p>
        )}
        {multi
          ? roles.map((r) => <Row key={r.id} id={r.id} label={r.name} />)
          : roles.map((r) => (
              <div key={r.id} className="px-3 py-2.5 rounded-lg border border-slate-200 text-sm text-slate-700">{r.name}</div>
            ))}
      </div>
    </div>
  );
}
