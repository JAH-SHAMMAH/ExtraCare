"use client";

import { useMemo, useState } from "react";
import { useStaff } from "@/hooks/useUsers";
import { cn, getInitials } from "@/lib/utils";
import { Users as UsersIcon, Search, AlertTriangle, Mail, Phone, Briefcase } from "lucide-react";

// The server already excludes teachers (job_title="Teacher") and students/
// parents. Admins are still distinguished here for the filter chips.
const roleSlugs = (u: any): string[] =>
  (u.roles ?? []).map((r: any) => (r.slug || r.name || "").toString().toLowerCase()).concat(u.primary_role ? [String(u.primary_role).toLowerCase()] : []);
const isAdmin = (u: any) => roleSlugs(u).some((s) => s === "org_admin" || s === "manager" || s === "admin");

type Filter = "all" | "admins" | "staff";

export default function StaffDirectoryPage() {
  const [search, setSearch] = useState("");
  const [filter, setFilter] = useState<Filter>("all");
  const { data, isLoading, isError, refetch } = useStaff({ search: search || undefined });

  const staff = useMemo(() => (data ?? []) as any[], [data]);

  const shown = useMemo(() => {
    if (filter === "admins") return staff.filter(isAdmin);
    if (filter === "staff") return staff.filter((u) => !isAdmin(u));
    return staff;
  }, [staff, filter]);

  return (
    <div className="p-8 max-w-6xl mx-auto">
      <div className="mb-6">
        <nav className="flex items-center gap-2 text-xs text-slate-400 mb-2"><span>People &amp; HR</span><span>/</span><span className="text-brand-600 font-semibold">Staff &amp; Admin</span></nav>
        <h1 className="text-2xl font-black text-slate-900 tracking-tight">Staff &amp; Admin</h1>
        <p className="text-slate-500 text-sm mt-0.5">Non-teaching staff and administrators. (Teaching staff are under <span className="font-medium">Teachers</span>.)</p>
      </div>

      <div className="flex flex-col md:flex-row md:items-center gap-3 mb-5">
        <div className="relative flex-1 max-w-sm"><Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" /><input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search staff…" className="input pl-9" /></div>
        <div className="flex gap-1 bg-slate-100 rounded-lg p-1">
          {([["all", "All"], ["admins", "Admins"], ["staff", "Staff"]] as [Filter, string][]).map(([k, l]) => (
            <button key={k} onClick={() => setFilter(k)} className={cn("px-3 py-1.5 text-xs font-semibold rounded-md transition", filter === k ? "bg-white text-brand-700 shadow-sm" : "text-slate-500 hover:text-slate-700")}>{l}</button>
          ))}
        </div>
      </div>

      {isLoading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">{Array.from({ length: 6 }).map((_, i) => <div key={i} className="h-28 bg-slate-100 rounded-xl animate-pulse" />)}</div>
      ) : isError ? (
        <div className="bg-white rounded-xl border border-slate-200 py-14 text-center"><AlertTriangle size={28} className="mx-auto mb-3 text-amber-400" /><p className="text-sm font-semibold text-slate-600">Couldn’t load staff.</p><button onClick={() => refetch()} className="mt-3 btn-secondary">Retry</button></div>
      ) : shown.length === 0 ? (
        <div className="bg-white rounded-xl border border-slate-200 flex flex-col items-center justify-center py-16 text-slate-400"><UsersIcon size={36} className="mb-3 opacity-40" /><p className="font-semibold">No staff found</p>{search && <p className="text-sm mt-1">Try a different search.</p>}</div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {shown.map((u) => (
            <div key={u.id} className="bg-white rounded-xl border border-slate-200 p-5">
              <div className="flex items-start gap-3 mb-3">
                <div className="w-11 h-11 rounded-lg bg-brand-600/10 flex items-center justify-center text-brand-700 font-bold shrink-0 overflow-hidden">
                  {u.avatar_url ? <img src={u.avatar_url} alt="" className="w-full h-full object-cover" /> : getInitials(u.full_name || u.email || "?")}
                </div>
                <div className="min-w-0 flex-1">
                  <p className="text-sm font-bold text-slate-900 truncate">{u.full_name || "—"}</p>
                  <p className="text-xs text-slate-500 truncate flex items-center gap-1"><Briefcase size={11} /> {u.job_title || "Staff"}{u.department ? ` · ${u.department}` : ""}</p>
                </div>
                {isAdmin(u) && <span className="badge bg-purple-50 text-purple-700 border-purple-200">Admin</span>}
              </div>
              <div className="space-y-1 text-xs text-slate-500">
                <p className="flex items-center gap-1.5 truncate"><Mail size={12} /> {u.email}</p>
                {u.phone && <p className="flex items-center gap-1.5"><Phone size={12} /> {u.phone}</p>}
              </div>
              <div className="mt-3 flex items-center justify-between">
                <span className={cn("badge capitalize", u.status === "active" ? "bg-emerald-50 text-emerald-700 border-emerald-200" : "bg-slate-50 text-slate-500 border-slate-200")}>{u.status}</span>
                <span className="text-[10px] font-semibold uppercase tracking-wide text-slate-400">{(roleSlugs(u)[0] || "staff").replace(/_/g, " ")}</span>
              </div>
            </div>
          ))}
        </div>
      )}

      <p className="text-xs text-slate-400 mt-5">{staff.length} staff &amp; admin account{staff.length === 1 ? "" : "s"}. Teaching staff appear under Teachers.</p>
    </div>
  );
}
