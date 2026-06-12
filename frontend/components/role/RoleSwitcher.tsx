"use client";

import { useEffect, useRef, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { ChevronDown, Check, Shield, GraduationCap, User, Users } from "lucide-react";
import { cn } from "@/lib/utils";
import { useAuthStore, type ActiveRole } from "@/lib/store";
import { useMyContexts } from "@/hooks/useMyContexts";

const ROLE_META: Record<ActiveRole, { label: string; color: string; icon: typeof Shield }> = {
  admin:   { label: "Admin",   color: "bg-brand-600",   icon: Shield },
  teacher: { label: "Teacher", color: "bg-emerald-600", icon: GraduationCap },
  parent:  { label: "Parent",  color: "bg-amber-600",   icon: Users },
  student: { label: "Student", color: "bg-indigo-600",  icon: User },
};

/**
 * Sits in the TopBar. Renders nothing when the user has a single role —
 * the TopBar stays clean for the 80% case. For multi-role users (the
 * demo hero), it's a pill showing the active role with a dropdown of
 * available lenses.
 *
 * Switching is instant: we mutate the store, invalidate role-scoped
 * queries (so the homepage re-renders with fresh data), and let the
 * dashboard page branch on activeRole.
 */
export function RoleSwitcher() {
  const qc = useQueryClient();
  const { activeRole, setActiveRole } = useAuthStore();
  const { data } = useMyContexts();
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function onClick(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    }
    if (open) document.addEventListener("mousedown", onClick);
    return () => document.removeEventListener("mousedown", onClick);
  }, [open]);

  const available = data?.available_roles ?? [];

  // Single-role users: invisible, no clutter.
  if (available.length <= 1) return null;
  // Store hasn't synced yet — invisible rather than flashing a wrong label.
  if (!activeRole) return null;

  const active = ROLE_META[activeRole];
  const ActiveIcon = active.icon;

  const handleSelect = (role: ActiveRole) => {
    if (role === activeRole) {
      setOpen(false);
      return;
    }
    setActiveRole(role);
    // Role-scoped queries (anything keyed off active role) are cheap to
    // refetch and must not show stale data after a switch. /me/contexts
    // itself is unchanged, so leave it in cache.
    qc.invalidateQueries({ queryKey: ["me", "contexts"], refetchType: "none" });
    setOpen(false);
  };

  return (
    <div className="relative" ref={ref}>
      <button
        onClick={() => setOpen((o) => !o)}
        className={cn(
          "flex items-center gap-2 px-3 h-9 rounded-lg border text-xs font-semibold transition-all",
          open
            ? "bg-slate-50 border-slate-300 text-slate-800"
            : "bg-white border-slate-200 text-slate-700 hover:bg-slate-50",
        )}
        aria-label="Switch role"
      >
        <span className={cn("w-2 h-2 rounded-full", active.color)} />
        <ActiveIcon size={14} className="text-slate-500" />
        <span>{active.label}</span>
        <ChevronDown size={12} className={cn("text-slate-400 transition-transform", open && "rotate-180")} />
      </button>

      {open && (
        <div className="absolute right-0 top-full mt-2 w-56 bg-white rounded-xl border border-slate-200 shadow-xl z-50 overflow-hidden">
          <div className="px-3 py-2 border-b border-slate-100">
            <p className="text-[10px] font-bold uppercase tracking-widest text-slate-400">View as</p>
          </div>
          <div className="py-1">
            {available.map((role) => {
              const meta = ROLE_META[role];
              const Icon = meta.icon;
              const isActive = role === activeRole;
              return (
                <button
                  key={role}
                  onClick={() => handleSelect(role)}
                  className={cn(
                    "w-full flex items-center gap-3 px-3 py-2 text-sm transition-colors",
                    isActive ? "bg-brand-50 text-brand-700" : "text-slate-700 hover:bg-slate-50",
                  )}
                >
                  <span className={cn("w-2 h-2 rounded-full", meta.color)} />
                  <Icon size={14} className={isActive ? "text-brand-600" : "text-slate-500"} />
                  <span className="flex-1 text-left font-medium">{meta.label}</span>
                  {isActive && <Check size={14} className="text-brand-600" />}
                </button>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
