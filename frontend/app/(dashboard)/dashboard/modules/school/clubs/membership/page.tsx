"use client";

import { useEffect, useMemo, useState } from "react";
import { useSessions } from "@/hooks/usePlatform";
import { useClubMembershipSummary, useClubMembersByTerm, useUpdateMembershipStatus } from "@/hooks/useSchoolExperience";
import { useHasPermission } from "@/components/guards/PermissionGate";
import { cn } from "@/lib/utils";
import { ClipboardList, Eye, ChevronLeft, Loader2, AlertTriangle, Check, Ban } from "lucide-react";
import type { ClubAccountRow, ClubMemberDetail } from "@/types";

function StatusBadge({ status }: { status: string }) {
  const map: Record<string, string> = { approved: "bg-emerald-50 text-emerald-700 border-emerald-200", pending: "bg-amber-50 text-amber-700 border-amber-200", withheld: "bg-rose-50 text-rose-700 border-rose-200" };
  return <span className={cn("badge uppercase", map[status] || "bg-slate-50 text-slate-500 border-slate-200")}>{status}</span>;
}

export default function ClubMembershipListPage() {
  const canWrite = useHasPermission("school:clubs:write");
  const { data: sessions } = useSessions();
  const rows = sessions ?? [];
  const sessionNames = useMemo(() => Array.from(new Set(rows.map((s: any) => s.name))), [rows]);
  const [session, setSession] = useState("");
  const [term, setTerm] = useState("");
  const termsFor = useMemo(() => Array.from(new Set(rows.filter((s: any) => s.name === session).map((s: any) => s.term).filter(Boolean))), [rows, session]);

  // Default to the current session/term once loaded.
  useEffect(() => {
    if (session || rows.length === 0) return;
    const cur = rows.find((s: any) => s.is_current) ?? rows[0];
    if (cur) { setSession(cur.name); setTerm(cur.term || ""); }
  }, [rows, session]);

  const { data, isLoading, isError, refetch } = useClubMembershipSummary({ academic_year: session || undefined, term: term || undefined });
  const [viewClub, setViewClub] = useState<ClubAccountRow | null>(null);

  const accounts: ClubAccountRow[] = data?.items ?? [];

  if (viewClub) return <ClubMemberList club={viewClub} session={session} term={term} canWrite={canWrite} onBack={() => setViewClub(null)} />;

  return (
    <div className="p-8 max-w-5xl mx-auto">
      <div className="mb-6">
        <nav className="flex items-center gap-2 text-xs text-slate-400 mb-2"><span>Clubs</span><span>/</span><span className="text-brand-600 font-semibold">Membership List</span></nav>
        <h1 className="text-2xl font-black text-slate-900 tracking-tight">Membership List</h1>
        <p className="text-slate-500 text-sm mt-0.5">Per-term club account summary — active, withheld, and pending members.</p>
      </div>

      <div className="bg-white rounded-xl border border-slate-200 p-5 mb-6 grid grid-cols-1 sm:grid-cols-2 gap-4 max-w-lg">
        <div><label className="label">Select Session</label><select value={session} onChange={(e) => { setSession(e.target.value); setTerm(""); }} className="input"><option value="">All</option>{sessionNames.map((n) => <option key={n} value={n}>{n}</option>)}</select></div>
        <div><label className="label">Select Term</label><select value={term} onChange={(e) => setTerm(e.target.value)} className="input"><option value="">All</option>{termsFor.map((t) => <option key={t} value={t}>{t}</option>)}</select></div>
      </div>

      <div className="bg-white rounded-xl border border-slate-200 overflow-x-auto">
        <div className="px-5 py-3 bg-brand-700 rounded-t-xl"><p className="text-white font-bold text-sm flex items-center gap-2"><ClipboardList size={16} /> Manage Club Information</p></div>
        <table className="w-full text-left">
          <thead><tr className="bg-slate-50/80 border-b border-slate-100">{["#", "Club Name", "Term", "Club Status", "Active", "Inactive", "Pending", "Actions"].map((h) => <th key={h} className="px-4 py-3 text-[10px] font-bold uppercase tracking-widest text-slate-500 whitespace-nowrap">{h}</th>)}</tr></thead>
          <tbody className="divide-y divide-slate-50">
            {isLoading ? Array.from({ length: 5 }).map((_, i) => <tr key={i}>{Array.from({ length: 8 }).map((_, j) => <td key={j} className="px-4 py-4"><div className="h-4 bg-slate-100 rounded animate-pulse w-12" /></td>)}</tr>)
            : isError ? <tr><td colSpan={8} className="py-14 text-center"><AlertTriangle size={26} className="mx-auto mb-2 text-amber-400" /><button onClick={() => refetch()} className="btn-secondary mt-2">Retry</button></td></tr>
            : accounts.length > 0 ? accounts.map((c, i) => (
              <tr key={c.club_id} className="hover:bg-slate-50/70">
                <td className="px-4 py-3 text-sm text-slate-500">{i + 1}</td>
                <td className="px-4 py-3 text-sm font-semibold text-slate-800">{c.club_name}</td>
                <td className="px-4 py-3 text-sm text-slate-500">{c.term || term || "—"}</td>
                <td className="px-4 py-3"><span className={cn("badge", c.club_status === "ACTIVE" ? "bg-emerald-50 text-emerald-700 border-emerald-200" : "bg-slate-50 text-slate-400 border-slate-200")}>{c.club_status}</span></td>
                <td className="px-4 py-3 text-sm font-bold text-emerald-600">{c.active_members}</td>
                <td className="px-4 py-3 text-sm font-bold text-rose-500">{c.inactive_members}</td>
                <td className="px-4 py-3 text-sm font-bold text-amber-600">{c.pending_requests}</td>
                <td className="px-4 py-3"><button onClick={() => setViewClub(c)} className="inline-flex items-center gap-1 text-xs font-semibold text-white bg-teal-500 hover:bg-teal-600 px-2.5 py-1.5 rounded"><Eye size={13} /> View Club Details</button></td>
              </tr>
            )) : <tr><td colSpan={8} className="py-16 text-center text-slate-400"><ClipboardList size={32} className="mx-auto mb-2 opacity-40" /><p className="font-semibold">No clubs</p></td></tr>}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function ClubMemberList({ club, session, term, canWrite, onBack }: { club: ClubAccountRow; session: string; term: string; canWrite: boolean; onBack: () => void }) {
  const { data, isLoading } = useClubMembersByTerm(club.club_id, { academic_year: session || undefined, term: term || undefined });
  const update = useUpdateMembershipStatus();
  const members: ClubMemberDetail[] = data?.items ?? [];

  return (
    <div className="p-8 max-w-5xl mx-auto">
      <div className="flex items-center justify-between mb-5">
        <div>
          <nav className="flex items-center gap-2 text-xs text-slate-400 mb-2"><span>Clubs</span><span>/</span><span>Membership List</span><span>/</span><span className="text-brand-600 font-semibold">{club.club_name}</span></nav>
          <h1 className="text-xl font-black text-slate-900">{club.club_name} Member List {session && <span className="text-slate-400 font-semibold">[{session}{term ? ` · ${term}` : ""}]</span>}</h1>
        </div>
        <button onClick={onBack} className="btn-secondary gap-1"><ChevronLeft size={15} /> Back to List</button>
      </div>

      <div className="bg-white rounded-xl border border-slate-200 overflow-x-auto">
        <table className="w-full text-left">
          <thead><tr className="bg-slate-50/80 border-b border-slate-100">{["#", "Student Name", "Current Class", "Club Name", "Membership Status", "Action"].map((h) => <th key={h} className="px-5 py-3 text-[10px] font-bold uppercase tracking-widest text-slate-500 whitespace-nowrap">{h}</th>)}</tr></thead>
          <tbody className="divide-y divide-slate-50">
            {isLoading ? <tr><td colSpan={6} className="px-5 py-10 text-center text-slate-400"><Loader2 className="animate-spin mx-auto" /></td></tr>
            : members.length > 0 ? members.map((m, i) => (
              <tr key={m.id} className="hover:bg-slate-50/70">
                <td className="px-5 py-3 text-sm text-slate-500">{i + 1}</td>
                <td className="px-5 py-3 text-sm font-semibold text-slate-800">{m.student_name || "—"}</td>
                <td className="px-5 py-3 text-sm text-slate-600">{m.current_class || "—"}</td>
                <td className="px-5 py-3 text-sm text-slate-600">{m.club_name}</td>
                <td className="px-5 py-3"><StatusBadge status={m.status} /></td>
                <td className="px-5 py-3">
                  {canWrite && (
                    <div className="flex items-center gap-1">
                      {m.status !== "approved" && <button onClick={() => update.mutate({ id: m.id, status: "approved" })} className="inline-flex items-center gap-1 text-xs font-semibold text-emerald-600 hover:text-emerald-700 px-2 py-1 rounded hover:bg-emerald-50"><Check size={13} /> Approve</button>}
                      {m.status !== "withheld" && <button onClick={() => update.mutate({ id: m.id, status: "withheld" })} className="inline-flex items-center gap-1 text-xs font-semibold text-rose-600 hover:text-rose-700 px-2 py-1 rounded hover:bg-rose-50"><Ban size={13} /> Withhold</button>}
                    </div>
                  )}
                </td>
              </tr>
            )) : <tr><td colSpan={6} className="py-14 text-center text-slate-400 font-semibold">No members for this term</td></tr>}
          </tbody>
        </table>
      </div>
    </div>
  );
}
