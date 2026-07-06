"use client";

import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { medicalApi } from "@/lib/api";
import { BarChart3, AlertTriangle } from "lucide-react";

export default function MedicalAnalysisPage() {
  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ["medical-records", "all"],
    queryFn: () => medicalApi.list({ page_size: 500 }),
  });
  const records: any[] = data?.items ?? [];

  const monthly = useMemo(() => {
    const buckets: { key: string; label: string; count: number }[] = [];
    const now = new Date();
    for (let i = 5; i >= 0; i--) {
      const d = new Date(now.getFullYear(), now.getMonth() - i, 1);
      buckets.push({ key: `${d.getFullYear()}-${d.getMonth()}`, label: d.toLocaleString(undefined, { month: "short" }), count: 0 });
    }
    records.forEach((r) => {
      const d = r.recorded_on ? new Date(r.recorded_on) : null;
      if (!d) return;
      const b = buckets.find((x) => x.key === `${d.getFullYear()}-${d.getMonth()}`);
      if (b) b.count += 1;
    });
    return buckets;
  }, [records]);

  const byType = useMemo(() => rank(records.map((r) => r.record_type || "visit")), [records]);
  const bySeverity = useMemo(() => rank(records.map((r) => r.severity || "unspecified")), [records]);
  const maxMonth = Math.max(1, ...monthly.map((m) => m.count));

  return (
    <div className="p-8 max-w-5xl mx-auto">
      <div className="mb-6">
        <nav className="flex items-center gap-2 text-xs text-slate-400 mb-2"><span>Medicals</span><span>/</span><span className="text-brand-600 font-semibold">Medical Analysis</span></nav>
        <h1 className="text-2xl font-black text-slate-900 tracking-tight">Medical Analysis</h1>
        <p className="text-slate-500 text-sm mt-0.5">Trends and distribution across clinic records.</p>
      </div>

      {isLoading ? (
        <div className="space-y-4">{Array.from({ length: 3 }).map((_, i) => <div key={i} className="h-40 bg-slate-100 rounded-xl animate-pulse" />)}</div>
      ) : isError ? (
        <div className="bg-white rounded-xl border border-slate-200 py-14 text-center"><AlertTriangle size={28} className="mx-auto mb-3 text-amber-400" /><p className="text-sm font-semibold text-slate-600">Couldn’t load analysis.</p><button onClick={() => refetch()} className="mt-3 btn-secondary">Retry</button></div>
      ) : records.length === 0 ? (
        <div className="bg-white rounded-xl border border-slate-200 flex flex-col items-center justify-center py-16 text-slate-400"><BarChart3 size={36} className="mb-3 opacity-40" /><p className="font-semibold">No data to analyse yet</p></div>
      ) : (
        <div className="space-y-4">
          <div className="bg-white rounded-xl border border-slate-200 p-5">
            <h2 className="text-sm font-bold text-slate-800 mb-5">Records per month (last 6)</h2>
            <div className="flex items-end justify-between gap-3 h-40">
              {monthly.map((m) => (
                <div key={m.key} className="flex-1 flex flex-col items-center justify-end h-full">
                  <span className="text-xs font-semibold text-slate-600 mb-1">{m.count}</span>
                  <div className="w-full bg-brand-500 rounded-t-md transition-all" style={{ height: `${(m.count / maxMonth) * 100}%`, minHeight: m.count ? "4px" : "0" }} />
                  <span className="text-[10px] text-slate-400 mt-2">{m.label}</span>
                </div>
              ))}
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <Ranked title="Most common record types" rows={byType} />
            <Ranked title="By severity" rows={bySeverity} />
          </div>
        </div>
      )}
    </div>
  );
}

function rank(arr: string[]): { key: string; count: number }[] {
  const m = arr.reduce((a, k) => { a[k] = (a[k] || 0) + 1; return a; }, {} as Record<string, number>);
  return Object.entries(m).map(([key, count]) => ({ key, count })).sort((a, b) => b.count - a.count);
}

function Ranked({ title, rows }: { title: string; rows: { key: string; count: number }[] }) {
  const max = Math.max(1, ...rows.map((r) => r.count));
  return (
    <div className="bg-white rounded-xl border border-slate-200 p-5">
      <h2 className="text-sm font-bold text-slate-800 mb-4">{title}</h2>
      <div className="space-y-2.5">
        {rows.map((r) => (
          <div key={r.key}>
            <div className="flex justify-between text-xs mb-1"><span className="capitalize text-slate-600">{r.key}</span><span className="font-semibold text-slate-700">{r.count}</span></div>
            <div className="h-2 rounded-full bg-slate-100 overflow-hidden"><div className="h-full bg-brand-500 rounded-full" style={{ width: `${(r.count / max) * 100}%` }} /></div>
          </div>
        ))}
      </div>
    </div>
  );
}
