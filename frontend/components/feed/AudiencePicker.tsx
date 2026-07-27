"use client";

import { useEffect, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Users2, ChevronDown, Check, Search, X, Loader2 } from "lucide-react";
import { cn, getInitials, resolveMediaUrl } from "@/lib/utils";
import { useAvailableRoles } from "@/hooks/useUsers";
import { usersApi } from "@/lib/api";
import type { AudienceUser } from "@/types";

/**
 * "Publish To" targeting for a new post — role checkboxes + a per-role "more"
 * that opens the Select Users modal for individuals. Controlled: the parent owns
 * the selected role slugs + user list. No selection = everyone (public). Reuses
 * the RBAC role list (/users/roles/available) — never a second maintained list.
 */
export function AudiencePicker({
  roles, users, onChange, disabled,
}: {
  roles: string[];
  users: AudienceUser[];
  onChange: (roles: string[], users: AudienceUser[]) => void;
  disabled?: boolean;
}) {
  const { data } = useAvailableRoles();
  const roleList: { id: string; slug: string; name: string }[] = data?.items ?? [];
  const [open, setOpen] = useState(false);
  const [modalRole, setModalRole] = useState<{ slug: string; name: string } | null>(null);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function onClick(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    }
    if (open) document.addEventListener("mousedown", onClick);
    return () => document.removeEventListener("mousedown", onClick);
  }, [open]);

  const isPublic = roles.length === 0 && users.length === 0;
  const summary = isPublic ? "Everyone" : [
    roles.length ? `${roles.length} role${roles.length > 1 ? "s" : ""}` : "",
    users.length ? `${users.length} ${users.length > 1 ? "people" : "person"}` : "",
  ].filter(Boolean).join(" · ");

  const toggleRole = (slug: string) =>
    onChange(roles.includes(slug) ? roles.filter((r) => r !== slug) : [...roles, slug], users);

  return (
    <div className="relative" ref={ref}>
      <button
        type="button" disabled={disabled} onClick={() => setOpen((o) => !o)}
        className={cn(
          "flex items-center gap-1.5 text-xs font-medium px-2.5 py-1.5 rounded-md border transition disabled:opacity-50",
          isPublic ? "border-slate-200 text-slate-600 hover:bg-slate-50" : "border-indigo-200 bg-indigo-50 text-indigo-700",
        )}
      >
        <Users2 className="w-3.5 h-3.5 shrink-0" />
        <span className="max-w-[150px] truncate">Publish to: {summary}</span>
        <ChevronDown className={cn("w-3.5 h-3.5 shrink-0 transition-transform", open && "rotate-180")} />
      </button>

      {open && (
        <div className="absolute right-0 bottom-full mb-2 w-72 max-h-80 overflow-y-auto bg-white rounded-xl border border-slate-200 shadow-xl z-40">
          <div className="px-3 py-2 border-b border-slate-100 sticky top-0 bg-white">
            <p className="text-[10px] font-bold uppercase tracking-widest text-slate-400">Publish to</p>
            <p className="text-[11px] text-slate-400 mt-0.5">No selection = everyone in your school.</p>
          </div>
          <div className="py-1">
            {roleList.map((r) => {
              const checked = roles.includes(r.slug);
              return (
                <div key={r.id} className="flex items-center gap-2 px-3 py-1.5 hover:bg-slate-50">
                  <button type="button" onClick={() => toggleRole(r.slug)} className="flex items-center gap-2 flex-1 text-left min-w-0">
                    <span className={cn("w-4 h-4 rounded border flex items-center justify-center shrink-0", checked ? "bg-indigo-600 border-indigo-600" : "border-slate-300")}>
                      {checked && <Check className="w-3 h-3 text-white" />}
                    </span>
                    <span className="text-sm text-slate-700 truncate">{r.name}</span>
                  </button>
                  <button type="button" onClick={() => setModalRole({ slug: r.slug, name: r.name })}
                    className="text-[11px] font-semibold text-indigo-600 hover:underline shrink-0">more</button>
                </div>
              );
            })}
          </div>
          {users.length > 0 && (
            <div className="px-3 py-2 border-t border-slate-100">
              <p className="text-[10px] font-bold uppercase tracking-widest text-slate-400 mb-1.5">Individuals ({users.length})</p>
              <div className="flex flex-wrap gap-1">
                {users.map((u) => (
                  <span key={u.id} className="inline-flex items-center gap-1 bg-slate-100 rounded-full pl-1 pr-1.5 py-0.5 text-xs text-slate-700">
                    <MiniAvatar u={u} />
                    <span className="max-w-[90px] truncate">{u.full_name}</span>
                    <button type="button" onClick={() => onChange(roles, users.filter((x) => x.id !== u.id))} className="text-slate-400 hover:text-red-500">
                      <X className="w-3 h-3" />
                    </button>
                  </span>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {modalRole && (
        <SelectUsersModal
          role={modalRole}
          selected={users}
          onClose={() => setModalRole(null)}
          onConfirm={(next) => { onChange(roles, next); setModalRole(null); }}
        />
      )}
    </div>
  );
}

function SelectUsersModal({
  role, selected, onClose, onConfirm,
}: {
  role: { slug: string; name: string };
  selected: AudienceUser[];
  onClose: () => void;
  onConfirm: (next: AudienceUser[]) => void;
}) {
  const [search, setSearch] = useState("");
  const [picked, setPicked] = useState<Record<string, AudienceUser>>(
    Object.fromEntries(selected.map((u) => [u.id, u])),
  );
  const { data, isLoading } = useQuery({
    queryKey: ["feed", "audience-users", role.slug, search],
    queryFn: () => usersApi.byRole(role.slug, search || undefined),
  });
  const list: AudienceUser[] = data?.items ?? [];

  const toggle = (u: AudienceUser) =>
    setPicked((prev) => {
      const next = { ...prev };
      if (next[u.id]) delete next[u.id]; else next[u.id] = u;
      return next;
    });

  return (
    <div className="fixed inset-0 z-50 bg-slate-900/40 flex items-center justify-center p-4" onClick={onClose}>
      <div className="bg-white rounded-xl border border-slate-200 shadow-xl w-full max-w-lg max-h-[80vh] flex flex-col" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between px-5 py-3 border-b border-slate-100">
          <h3 className="text-sm font-bold text-slate-800">Select Users · {role.name}</h3>
          <button onClick={onClose} className="text-slate-400 hover:text-slate-600"><X className="w-4 h-4" /></button>
        </div>
        <div className="px-5 py-3">
          <div className="relative">
            <Search className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
            <input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search name or email…" autoFocus
              className="w-full text-sm pl-9 pr-3 py-2 rounded-lg border border-slate-200 focus:outline-none focus:ring-2 focus:ring-indigo-500/40 placeholder:text-slate-400" />
          </div>
        </div>
        <div className="flex-1 overflow-y-auto px-2 pb-2 min-h-[8rem]">
          {isLoading ? (
            <div className="py-10 flex justify-center"><Loader2 className="w-5 h-5 animate-spin text-slate-400" /></div>
          ) : list.length === 0 ? (
            <p className="text-center text-sm text-slate-400 py-8">No users in this role.</p>
          ) : (
            list.map((u) => {
              const on = !!picked[u.id];
              return (
                <button key={u.id} type="button" onClick={() => toggle(u)}
                  className={cn("w-full flex items-center gap-3 px-3 py-2 rounded-lg text-left transition", on ? "bg-indigo-50" : "hover:bg-slate-50")}>
                  <MiniAvatar u={u} size="md" />
                  <span className="flex-1 text-sm text-slate-700 truncate">{u.full_name}</span>
                  <span className={cn("w-4 h-4 rounded border flex items-center justify-center shrink-0", on ? "bg-indigo-600 border-indigo-600" : "border-slate-300")}>
                    {on && <Check className="w-3 h-3 text-white" />}
                  </span>
                </button>
              );
            })
          )}
        </div>
        <div className="flex items-center justify-between px-5 py-3 border-t border-slate-100">
          <span className="text-xs text-slate-500">{Object.keys(picked).length} selected</span>
          <div className="flex gap-2">
            <button onClick={onClose} className="text-sm px-3 py-1.5 rounded-lg border border-slate-200 text-slate-600 hover:bg-slate-50">Cancel</button>
            <button onClick={() => onConfirm(Object.values(picked))} className="text-sm px-3 py-1.5 rounded-lg bg-indigo-600 text-white hover:bg-indigo-700">Done</button>
          </div>
        </div>
      </div>
    </div>
  );
}

function MiniAvatar({ u, size = "sm" }: { u: AudienceUser; size?: "sm" | "md" }) {
  const px = size === "md" ? "w-8 h-8 text-xs" : "w-5 h-5 text-[9px]";
  if (u.avatar_url) {
    return <img src={resolveMediaUrl(u.avatar_url)} alt="" className={cn(px, "rounded-full object-cover bg-slate-100 shrink-0")} />;
  }
  return (
    <span className={cn(px, "rounded-full bg-indigo-100 text-indigo-700 font-semibold flex items-center justify-center shrink-0")}>
      {getInitials(u.full_name)}
    </span>
  );
}
