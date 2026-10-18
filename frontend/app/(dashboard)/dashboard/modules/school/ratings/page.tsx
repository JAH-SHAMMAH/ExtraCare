"use client";

import { useState } from "react";
import { useRatingsSummary, useTeacherRatings } from "@/hooks/useSchool";
import { cn, getInitials } from "@/lib/utils";
import { Star, Loader2, EyeOff } from "lucide-react";
import type { TeacherRating } from "@/types";

function Stars({ value }: { value: number }) {
  return (
    <div className="flex items-center gap-0.5">
      {[1, 2, 3, 4, 5].map((n) => (<Star key={n} size={16} className={cn(n <= value ? "fill-amber-400 text-amber-400" : "text-slate-300")} />))}
    </div>
  );
}

/** Admin view: every rated teacher with average + count; open one for the breakdown and comments. */
export default function RatingsPage() {
  const { data: summary = [], isLoading } = useRatingsSummary();
  const [selected, setSelected] = useState("");
  const { data: ratings, isLoading: ratingsLoading } = useTeacherRatings({ teacher_id: selected || undefined });
  const list: TeacherRating[] = selected ? (ratings?.items || (Array.isArray(ratings) ? ratings : [])) : [];
  const pick = summary.find((s) => s.teacher_id === selected);

  return (
    <div className="p-4 sm:p-8 max-w-7xl mx-auto">
      <div className="mb-8">
        <nav className="flex items-center gap-2 text-xs text-slate-400 mb-2"><span>Staff Management</span><span>/</span><span className="text-brand-600 font-semibold">Teacher Ratings</span></nav>
        <h1 className="text-2xl font-black text-slate-900 tracking-tight">Teacher Ratings</h1>
        <p className="text-slate-500 text-sm mt-0.5">What pupils think of their teachers. Pupils rate from <b>Rate My Teachers</b> in their own portal; some choose to stay anonymous.</p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="bg-white rounded-xl border border-slate-200 overflow-hidden max-h-[600px] overflow-y-auto">
          {isLoading ? (<div className="p-8 text-center"><Loader2 size={20} className="animate-spin text-slate-400 mx-auto" /></div>)
          : summary.length === 0 ? (<div className="p-8 text-center text-slate-400 text-sm">No ratings yet. They appear here once pupils start rating.</div>)
          : summary.map((t) => (
            <button key={t.teacher_id} onClick={() => setSelected(t.teacher_id)}
              className={cn("w-full flex items-center gap-3 px-4 py-3 border-b border-slate-50 hover:bg-slate-50 text-left", selected === t.teacher_id && "bg-brand-50")}>
              <div className="w-9 h-9 rounded-lg bg-emerald-600/10 flex items-center justify-center text-emerald-700 text-xs font-bold shrink-0">{getInitials(t.name)}</div>
              <div className="min-w-0 flex-1"><p className="text-sm font-medium text-slate-900 truncate">{t.name}</p><p className="text-xs text-slate-400">{t.count} rating{t.count !== 1 ? "s" : ""}</p></div>
              <div className="text-right"><p className="text-sm font-bold text-slate-900">{t.average.toFixed(1)}</p><Star size={12} className="fill-amber-400 text-amber-400 ml-auto" /></div>
            </button>
          ))}
        </div>

        <div className="lg:col-span-2 space-y-6">
          {!pick ? (
            <div className="bg-white rounded-xl border border-slate-200 py-16 text-center text-slate-400"><Star size={40} className="mx-auto mb-3 opacity-40" /><p className="font-semibold">Select a teacher</p><p className="text-sm mt-1">See their average, spread and comments.</p></div>
          ) : (
            <>
              <div className="bg-white rounded-xl border border-slate-200 p-6 flex items-center gap-6">
                <div className="text-center"><p className="text-3xl font-black text-slate-900">{pick.average.toFixed(1)}</p><Stars value={Math.round(pick.average)} /><p className="text-xs text-slate-400 mt-1">{pick.count} rating{pick.count !== 1 ? "s" : ""}</p></div>
                <div className="flex-1 space-y-1">
                  {[5, 4, 3, 2, 1].map((n) => { const c = list.filter((r) => r.rating === n).length; const pct = list.length ? (c / list.length) * 100 : 0; return (
                    <div key={n} className="flex items-center gap-2"><span className="text-xs text-slate-500 w-3">{n}</span><div className="flex-1 bg-slate-100 rounded-full h-2"><div className="bg-amber-400 rounded-full h-full" style={{ width: `${pct}%` }} /></div><span className="text-xs text-slate-400 w-6">{c}</span></div>
                  ); })}
                </div>
              </div>
              <div className="bg-white rounded-xl border border-slate-200 p-6">
                <h3 className="text-sm font-bold text-slate-800 mb-4">Comments</h3>
                {ratingsLoading ? (<div className="text-center py-4"><Loader2 size={20} className="animate-spin text-slate-400 mx-auto" /></div>)
                : list.length === 0 ? (<p className="text-sm text-slate-400 text-center py-4">No ratings yet.</p>)
                : (<div className="space-y-3">{list.map((r) => (
                  <div key={r.id} className="p-3 bg-slate-50 rounded-lg border border-slate-100">
                    <div className="flex items-center justify-between mb-1">
                      <Stars value={r.rating} />
                      <span className="text-[11px] text-slate-500 inline-flex items-center gap-1">{(r as any).is_anonymous && <EyeOff size={12} />}{r.student_name || "Pupil"}</span>
                    </div>
                    {r.comment ? <p className="text-sm text-slate-700">{r.comment}</p> : <p className="text-xs text-slate-400">No comment.</p>}
                  </div>
                ))}</div>)}
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
