"use client";

import { useMemo } from "react";
import Link from "next/link";
import { useStaffAssessments } from "@/hooks/usePeople";
import { cn, formatDate } from "@/lib/utils";
import { Star, TrendingUp, ClipboardCheck, AlertTriangle, ArrowUpRight } from "lucide-react";

export default function PerformancePage() {
  const { data, isLoading, isError, refetch } = useStaffAssessments({ page_size: 200 });
  const reviews: any[] = data?.items ?? [];

  const stats = useMemo(() => {
    const rated = reviews.filter((r) => typeof r.overall_rating === "number");
    const avg = rated.length ? rated.reduce((s, r) => s + r.overall_rating, 0) / rated.length : 0;
    const dist = [1, 2, 3, 4, 5].map((n) => ({ n, count: rated.filter((r) => r.overall_rating === n).length }));
    const finalised = reviews.filter((r) => r.status && r.status !== "draft").length;
    return { total: reviews.length, avg, dist, finalised, draft: reviews.length - finalised, reviewed: new Set(reviews.map((r) => r.staff_user_id)).size };
  }, [reviews]);

  const maxDist = Math.max(1, ...stats.dist.map((d) => d.count));

  return (
    <div className="p-8 max-w-5xl mx-auto">
      <div className="flex flex-col md:flex-row md:items-end justify-between mb-6 gap-4">
        <div>
          <nav className="flex items-center gap-2 text-xs text-slate-400 mb-2"><span>HR Manager</span><span>/</span><span className="text-brand-600 font-semibold">Performance</span></nav>
          <h1 className="text-2xl font-black text-slate-900 tracking-tight">Performance Reviews</h1>
          <p className="text-slate-500 text-sm mt-0.5">Appraisal analytics across your staff. Manage individual reviews under Staff Assessment.</p>
        </div>
        <Link href="/dashboard/modules/school/staff-assessment" className="btn-secondary gap-2"><ClipboardCheck size={15} /> Manage reviews <ArrowUpRight size={13} /></Link>
      </div>

      {isLoading ? (
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">{Array.from({ length: 4 }).map((_, i) => <div key={i} className="h-24 bg-slate-100 rounded-xl animate-pulse" />)}</div>
      ) : isError ? (
        <div className="bg-white rounded-xl border border-slate-200 py-14 text-center"><AlertTriangle size={28} className="mx-auto mb-3 text-amber-400" /><p className="text-sm font-semibold text-slate-600">Couldn’t load reviews.</p><button onClick={() => refetch()} className="mt-3 btn-secondary">Retry</button></div>
      ) : reviews.length === 0 ? (
        <div className="bg-white rounded-xl border border-slate-200 flex flex-col items-center justify-center py-16 text-slate-400"><Star size={36} className="mb-3 opacity-40" /><p className="font-semibold">No performance reviews yet</p><Link href="/dashboard/modules/school/staff-assessment" className="mt-3 btn-primary">Create the first review</Link></div>
      ) : (
        <>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
            <Stat icon={ClipboardCheck} label="Total Reviews" value={String(stats.total)} accent="from-indigo-500 to-violet-600" />
            <Stat icon={Star} label="Avg Rating" value={`${stats.avg.toFixed(1)} / 5`} accent="from-amber-500 to-orange-600" />
            <Stat icon={TrendingUp} label="Staff Reviewed" value={String(stats.reviewed)} accent="from-emerald-500 to-teal-600" />
            <Stat icon={ClipboardCheck} label="Finalised" value={`${stats.finalised}/${stats.total}`} accent="from-sky-500 to-blue-600" />
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="bg-white rounded-xl border border-slate-200 p-5">
              <h2 className="text-sm font-bold text-slate-800 mb-4">Rating distribution</h2>
              <div className="space-y-2.5">
                {stats.dist.slice().reverse().map((d) => (
                  <div key={d.n}>
                    <div className="flex justify-between text-xs mb-1"><span className="text-slate-600 flex items-center gap-1">{d.n} <Star size={11} className="text-amber-400 fill-amber-400" /></span><span className="font-semibold text-slate-700">{d.count}</span></div>
                    <div className="h-2 rounded-full bg-slate-100 overflow-hidden"><div className="h-full bg-amber-400 rounded-full" style={{ width: `${(d.count / maxDist) * 100}%` }} /></div>
                  </div>
                ))}
              </div>
            </div>
            <div className="bg-white rounded-xl border border-slate-200 p-5">
              <h2 className="text-sm font-bold text-slate-800 mb-4">Recent reviews</h2>
              <div className="divide-y divide-slate-50">
                {reviews.slice(0, 6).map((r) => (
                  <div key={r.id} className="flex items-center gap-3 py-2.5">
                    <div className="min-w-0 flex-1"><p className="text-sm font-medium text-slate-800 truncate">{r.staff_name || "—"}</p><p className="text-xs text-slate-400">{r.period}{r.review_date ? ` · ${formatDate(r.review_date)}` : ""}</p></div>
                    {typeof r.overall_rating === "number" && <span className="inline-flex items-center gap-1 text-sm font-bold text-amber-600">{r.overall_rating}<Star size={12} className="fill-amber-400 text-amber-400" /></span>}
                    <span className={cn("badge capitalize", r.status === "draft" ? "bg-slate-50 text-slate-500 border-slate-200" : "bg-emerald-50 text-emerald-700 border-emerald-200")}>{r.status || "—"}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </>
      )}
    </div>
  );
}

function Stat({ icon: Icon, label, value, accent }: { icon: any; label: string; value: string; accent: string }) {
  return (
    <div className={`rounded-xl p-5 text-white bg-gradient-to-br ${accent}`}>
      <Icon size={18} className="opacity-80 mb-2" />
      <p className="text-2xl font-black">{value}</p>
      <p className="text-xs font-semibold opacity-90 mt-1">{label}</p>
    </div>
  );
}
