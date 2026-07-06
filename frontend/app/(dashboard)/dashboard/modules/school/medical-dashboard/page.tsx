"use client";

import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { medicalApi } from "@/lib/api";
import { cn, formatDate } from "@/lib/utils";
import { Stethoscope, CalendarClock, Activity, Users2, AlertTriangle } from "lucide-react";

export default function MedicalDashboardPage() {
  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ["medical-records", "all"],
    queryFn: () => medicalApi.list({ page_size: 500 }),
  });
  const records: any[] = data?.items ?? [];

  const stats = useMemo(() => {
    const now = new Date();
    const thisMonth = records.filter((r) => r.recorded_on && new Date(r.recorded_on).getMonth() === now.getMonth() && new Date(r.recorded_on).getFullYear() === now.getFullYear()).length;
    const upcoming = records.filter((r) => r.follow_up_on && new Date(r.follow_up_on) >= new Date(now.toDateString())).length;
    const students = new Set(records.map((r) => r.student_id)).size;
    const bySeverity = tally(records.map((r) => r.severity || "unspecified"));
    const byType = tally(records.map((r) => r.record_type || "visit"));
    return { total: records.length, thisMonth, upcoming, students, bySeverity, byType };
  }, [records]);

  const followUps = useMemo(
    () => records.filter((r) => r.follow_up_on && new Date(r.follow_up_on) >= new Date(new Date().toDateString())).sort((a, b) => +new Date(a.follow_up_on) - +new Date(b.follow_up_on)).slice(0, 6),
    [records],
  );

  return (
    <div className="p-8 max-w-6xl mx-auto">
      <div className="mb-6">
        <nav className="flex items-center gap-2 text-xs text-slate-400 mb-2"><span>Medicals</span><span>/</span><span className="text-brand-600 font-semibold">Medical Dashboard</span></nav>
        <h1 className="text-2xl font-black text-slate-900 tracking-tight">Medical Dashboard</h1>
        <p className="text-slate-500 text-sm mt-0.5">Overview of the school clinic — confidential health data (nurse/admin only).</p>
      </div>

      {isLoading ? (
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">{Array.from({ length: 4 }).map((_, i) => <div key={i} className="h-24 bg-slate-100 rounded-xl animate-pulse" />)}</div>
      ) : isError ? (
        <div className="bg-white rounded-xl border border-slate-200 py-14 text-center"><AlertTriangle size={28} className="mx-auto mb-3 text-amber-400" /><p className="text-sm font-semibold text-slate-600">Couldn’t load medical data.</p><button onClick={() => refetch()} className="mt-3 btn-secondary">Retry</button></div>
      ) : records.length === 0 ? (
        <div className="bg-white rounded-xl border border-slate-200 flex flex-col items-center justify-center py-16 text-slate-400"><Stethoscope size={36} className="mb-3 opacity-40" /><p className="font-semibold">No medical records yet</p></div>
      ) : (
        <>
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">
            <Stat icon={Stethoscope} label="Total Records" value={stats.total} accent="from-emerald-500 to-teal-600" />
            <Stat icon={Activity} label="This Month" value={stats.thisMonth} accent="from-blue-500 to-indigo-600" />
            <Stat icon={CalendarClock} label="Upcoming Follow-ups" value={stats.upcoming} accent="from-amber-500 to-orange-600" />
            <Stat icon={Users2} label="Students Seen" value={stats.students} accent="from-fuchsia-500 to-purple-600" />
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <Breakdown title="By severity" data={stats.bySeverity} />
            <Breakdown title="By record type" data={stats.byType} />
          </div>

          <div className="bg-white rounded-xl border border-slate-200 mt-4">
            <h2 className="text-sm font-bold text-slate-800 px-5 py-3 border-b border-slate-100">Upcoming follow-ups</h2>
            {followUps.length === 0 ? <p className="text-sm text-slate-400 py-8 text-center">None scheduled.</p> : (
              <div className="divide-y divide-slate-50">
                {followUps.map((r) => (
                  <div key={r.id} className="flex items-center gap-3 px-5 py-3">
                    <span className="text-sm font-medium text-slate-800 flex-1 truncate">{r.student_name || "—"} · {r.title || r.record_type}</span>
                    <span className="text-xs text-amber-600 font-semibold">{formatDate(r.follow_up_on)}</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        </>
      )}
    </div>
  );
}

function tally(arr: string[]): Record<string, number> {
  return arr.reduce((acc, k) => { acc[k] = (acc[k] || 0) + 1; return acc; }, {} as Record<string, number>);
}

function Stat({ icon: Icon, label, value, accent }: { icon: any; label: string; value: number; accent: string }) {
  return (
    <div className={`rounded-xl p-5 text-white bg-gradient-to-br ${accent}`}>
      <Icon size={18} className="opacity-80 mb-2" />
      <p className="text-2xl font-black">{value}</p>
      <p className="text-xs font-semibold opacity-90 mt-1">{label}</p>
    </div>
  );
}

function Breakdown({ title, data }: { title: string; data: Record<string, number> }) {
  const entries = Object.entries(data).sort((a, b) => b[1] - a[1]);
  const max = Math.max(1, ...entries.map(([, v]) => v));
  return (
    <div className="bg-white rounded-xl border border-slate-200 p-5">
      <h2 className="text-sm font-bold text-slate-800 mb-4">{title}</h2>
      <div className="space-y-2.5">
        {entries.map(([k, v]) => (
          <div key={k}>
            <div className="flex justify-between text-xs mb-1"><span className="capitalize text-slate-600">{k}</span><span className="font-semibold text-slate-700">{v}</span></div>
            <div className="h-2 rounded-full bg-slate-100 overflow-hidden"><div className="h-full bg-brand-500 rounded-full" style={{ width: `${(v / max) * 100}%` }} /></div>
          </div>
        ))}
      </div>
    </div>
  );
}
