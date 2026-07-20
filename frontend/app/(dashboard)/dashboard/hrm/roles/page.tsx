"use client";

import { useState } from "react";
import { useAvailableRoles, useStaff, useAssignRoles } from "@/hooks/useUsers";
import { useHasPermission } from "@/components/guards/PermissionGate";
import { cn, getInitials } from "@/lib/utils";
import { ShieldCheck, Users as UsersIcon, ChevronDown, X, Loader2, AlertTriangle, Lock, Search } from "lucide-react";

export default function RolesPermissionsPage() {
  const canWrite = useHasPermission("roles:write");
  const { data: rolesData, isLoading: rolesLoading } = useAvailableRoles();
  const [search, setSearch] = useState("");
  const { data: staff, isLoading: staffLoading, isError, refetch } = useStaff({ search: search || undefined });
  const roles: any[] = rolesData?.items ?? [];

  return (
    <div className="p-8 max-w-5xl mx-auto">
      <div className="mb-6">
        <nav className="flex items-center gap-2 text-xs text-slate-400 mb-2"><span>HR Manager</span><span>/</span><span className="text-brand-600 font-semibold">Roles &amp; Permissions</span></nav>
        <h1 className="text-2xl font-black text-slate-900 tracking-tight">Roles &amp; Permissions</h1>
        <p className="text-slate-500 text-sm mt-0.5">Roles, their permissions, and who holds them.</p>
      </div>

      {/* Roles + permissions */}
      <h2 className="text-sm font-bold text-slate-800 mb-3 flex items-center gap-2"><ShieldCheck size={16} className="text-brand-600" /> Roles</h2>
      {rolesLoading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3 mb-8">{Array.from({ length: 4 }).map((_, i) => <div key={i} className="h-20 bg-slate-100 rounded-xl animate-pulse" />)}</div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3 mb-8">
          {roles.map((r) => <RoleCard key={r.id} role={r} />)}
        </div>
      )}

      {/* Members + role assignment */}
      <div className="flex items-center justify-between mb-3">
        <h2 className="text-sm font-bold text-slate-800 flex items-center gap-2"><UsersIcon size={16} className="text-brand-600" /> Members</h2>
        <div className="relative max-w-xs"><Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" /><input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search staff…" className="input pl-9 py-1.5 text-sm" /></div>
      </div>
      {staffLoading ? (
        <div className="space-y-2">{Array.from({ length: 5 }).map((_, i) => <div key={i} className="h-14 bg-slate-100 rounded-lg animate-pulse" />)}</div>
      ) : isError ? (
        <div className="bg-white rounded-xl border border-slate-200 py-12 text-center"><AlertTriangle size={26} className="mx-auto mb-3 text-amber-400" /><p className="text-sm font-semibold text-slate-600">Couldn’t load members.</p><button onClick={() => refetch()} className="mt-3 btn-secondary">Retry</button></div>
      ) : (staff ?? []).length === 0 ? (
        <div className="bg-white rounded-xl border border-slate-200 py-12 text-center text-slate-400"><p className="font-semibold">No members found</p></div>
      ) : (
        <div className="bg-white rounded-xl border border-slate-200 divide-y divide-slate-50">
          {(staff as any[]).map((u) => <MemberRow key={u.id} user={u} roles={roles} canWrite={canWrite} />)}
        </div>
      )}
      {!canWrite && <p className="text-xs text-slate-400 mt-4 flex items-center gap-1"><Lock size={12} /> Changing roles requires the roles:write capability (admin).</p>}
    </div>
  );
}

function RoleCard({ role }: { role: any }) {
  const [open, setOpen] = useState(false);
  const perms: string[] = role.permissions ?? [];
  return (
    <div className="bg-white rounded-xl border border-slate-200 p-4">
      <button onClick={() => setOpen((o) => !o)} className="w-full flex items-center justify-between">
        <div className="text-left">
          <p className="text-sm font-bold text-slate-900 capitalize">{role.name?.replace(/_/g, " ")}</p>
          <p className="text-xs text-slate-400">{perms.length} permission{perms.length === 1 ? "" : "s"}{role.is_system ? " · system" : ""}</p>
        </div>
        <ChevronDown size={15} className={cn("text-slate-400 transition-transform", open && "rotate-180")} />
      </button>
      {open && (
        <div className="mt-3 flex flex-wrap gap-1.5">
          {perms.length === 0 ? <span className="text-xs text-slate-400">No explicit permissions.</span> : perms.map((p) => (
            <span key={p} className="text-[10px] font-mono bg-slate-50 text-slate-600 border border-slate-200 rounded px-1.5 py-0.5">{p}</span>
          ))}
        </div>
      )}
    </div>
  );
}

function MemberRow({ user, roles, canWrite }: { user: any; roles: any[]; canWrite: boolean }) {
  const assign = useAssignRoles();
  const [editing, setEditing] = useState(false);
  const current: string[] = (user.roles ?? []).map((r: any) => r.id);
  const [sel, setSel] = useState<string[]>(current);

  const toggle = (id: string) => setSel((s) => (s.includes(id) ? s.filter((x) => x !== id) : [...s, id]));
  const save = () => assign.mutate({ id: user.id, role_ids: sel }, { onSuccess: () => setEditing(false) });

  return (
    <div className="px-5 py-3.5">
      <div className="flex items-center gap-3">
        <div className="w-9 h-9 rounded-lg bg-slate-100 flex items-center justify-center text-slate-500 text-xs font-bold shrink-0">{getInitials(user.full_name || user.email || "?")}</div>
        <div className="min-w-0 flex-1">
          <p className="text-sm font-semibold text-slate-800 truncate">{user.full_name || "—"}</p>
          <p className="text-xs text-slate-400 truncate">{user.email}</p>
        </div>
        <div className="flex items-center gap-1.5 flex-wrap justify-end">
          {(user.roles ?? []).map((r: any) => <span key={r.id} className="badge bg-brand-50 text-brand-700 border-brand-200 capitalize">{(r.name || r.slug)?.replace(/_/g, " ")}</span>)}
          {(user.roles ?? []).length === 0 && <span className="text-xs text-slate-400">no roles</span>}
        </div>
        {canWrite && <button onClick={() => { setSel(current); setEditing((e) => !e); }} className="text-xs font-semibold text-brand-600 hover:text-brand-700 shrink-0">{editing ? "Cancel" : "Edit"}</button>}
      </div>
      {editing && canWrite && (
        <div className="mt-3 pl-12">
          <div className="flex flex-wrap gap-2 mb-3">
            {roles.map((r) => (
              <button key={r.id} onClick={() => toggle(r.id)} className={cn("text-xs font-semibold rounded-lg border px-2.5 py-1 capitalize transition", sel.includes(r.id) ? "bg-brand-600 text-white border-brand-600" : "bg-white text-slate-600 border-slate-200 hover:border-brand-300")}>
                {(r.name || r.slug)?.replace(/_/g, " ")}
              </button>
            ))}
          </div>
          <button onClick={save} disabled={assign.isPending} className="btn-primary gap-2 text-sm py-1.5">{assign.isPending && <Loader2 size={14} className="animate-spin" />}Save roles</button>
        </div>
      )}
    </div>
  );
}
