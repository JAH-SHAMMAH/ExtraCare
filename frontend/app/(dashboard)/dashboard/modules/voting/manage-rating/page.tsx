"use client";

import { useState } from "react";
import { useVSessions, usePeriods } from "@/hooks/useVoting";
import { useSections } from "@/hooks/usePlatform";
import { cn } from "@/lib/utils";
import { BarChart3, AlertTriangle } from "lucide-react";

const STATUS_STYLE: Record<string, string> = { draft: "bg-slate-100 text-slate-500 border-slate-200", open: "bg-emerald-50 text-emerald-700 border-emerald-200", conducted: "bg-blue-50 text-blue-700 border-blue-200", active: "bg-emerald-50 text-emerald-700 border-emerald-200", ended: "bg-slate-100 text-slate-500 border-slate-200" };

export default function ManageRatingPage() {
  const [sectionId, setSectionId] = useState("");
  const { data: sections } = useSections();
  const { data: periods, isLoading: pl } = usePeriods();
  const { data: sessions, isLoading: sl, isError, refetch } = useVSessions();
  const sectionList: any[] = (sections as any[]) ?? [];
  const periodRows = (periods ?? []).filter((p) => !sectionId || p.section_id === sectionId);
  const sessionRows = (sessions ?? []).filter((s) => !sectionId || s.section_id === sectionId);

  return (
    <div className="p-8 max-w-4xl mx-auto">
      <div className="mb-6">
        <nav className="flex items-center gap-2 text-xs text-slate-400 mb-2"><span>Voting System</span><span>/</span><span className="text-brand-600 font-semibold">Manage Rating</span></nav>
        <h1 className="text-2xl font-black text-slate-900 tracking-tight">Manage Rating</h1>
        <p className="text-slate-500 text-sm mt-0.5">Overview of voting periods and sessions across your schools.</p>
      </div>

      <div className="flex flex-wrap gap-2 mb-5">
        <select value={sectionId} onChange={(e) => setSectionId(e.target.value)} className="input max-w-[220px]"><option value="">All schools</option>{sectionList.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}</select>
      </div>

      {isError ? (
        <div className="bg-white rounded-xl border border-slate-200 py-14 text-center"><AlertTriangle size={28} className="mx-auto mb-3 text-amber-400" /><p className="text-sm font-semibold text-slate-600">Couldn’t load.</p><button onClick={() => refetch()} className="mt-3 btn-secondary">Retry</button></div>
      ) : (
        <div className="space-y-6">
          <div>
            <h2 className="text-sm font-bold text-slate-800 mb-2">Voting Periods</h2>
            {pl ? <div className="h-14 bg-slate-100 rounded-lg animate-pulse" /> : periodRows.length === 0 ? (
              <div className="bg-white rounded-xl border border-slate-200 py-8 text-center text-sm text-slate-400">No periods.</div>
            ) : (
              <div className="bg-white rounded-xl border border-slate-200 divide-y divide-slate-50">
                {periodRows.map((p) => (
                  <div key={p.id} className="flex items-center justify-between px-5 py-3">
                    <span className="text-sm font-semibold text-slate-800">{p.name}{p.section_name ? ` · ${p.section_name}` : ""}</span>
                    <span className={cn("badge capitalize", STATUS_STYLE[p.status])}>{p.status}</span>
                  </div>
                ))}
              </div>
            )}
          </div>

          <div>
            <h2 className="text-sm font-bold text-slate-800 mb-2">Vote Sessions</h2>
            {sl ? <div className="h-14 bg-slate-100 rounded-lg animate-pulse" /> : sessionRows.length === 0 ? (
              <div className="bg-white rounded-xl border border-slate-200 flex flex-col items-center justify-center py-12 text-slate-400"><BarChart3 size={30} className="mb-2 opacity-40" /><p className="font-semibold">No sessions</p></div>
            ) : (
              <div className="bg-white rounded-xl border border-slate-200 divide-y divide-slate-50">
                {sessionRows.map((s) => (
                  <div key={s.id} className="flex items-center gap-3 px-5 py-3.5">
                    <div className="min-w-0 flex-1">
                      <p className="text-sm font-semibold text-slate-800 truncate">{s.title}</p>
                      <p className="text-xs text-slate-400">{s.candidate_count} candidates · {s.total_ballots} votes</p>
                    </div>
                    <span className={cn("badge capitalize", STATUS_STYLE[s.status] ?? STATUS_STYLE.draft)}>{s.status}</span>
                    {s.result_published && <span className="badge bg-amber-50 text-amber-700 border-amber-200">Published</span>}
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
