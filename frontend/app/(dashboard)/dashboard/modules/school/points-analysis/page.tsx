"use client";

import { useState } from "react";
import { usePointsAnalysis } from "@/hooks/usePastoral";
import { useSections, useHouses } from "@/hooks/usePlatform";
import { pastoralApi } from "@/lib/api";
import { cn } from "@/lib/utils";
import { Loader2, BarChart3, Download } from "lucide-react";
import { toast } from "sonner";

export default function PointsAnalysisPage() {
  const [section, setSection] = useState("");
  const [house, setHouse] = useState("");
  const params = { section: section || undefined, house: house || undefined };
  const { data: rows = [], isLoading } = usePointsAnalysis(params);
  const { data: sections = [] } = useSections();
  const { data: houses = [] } = useHouses();
  const [exporting, setExporting] = useState(false);

  const exportCsv = async () => {
    setExporting(true);
    try {
      const blob = await pastoralApi.points.analysisCsv(params);
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url; a.download = "points-analysis.csv"; a.click();
      URL.revokeObjectURL(url);
    } catch {
      toast.error("Export failed.");
    } finally {
      setExporting(false);
    }
  };

  const cols: [string, string][] = [
    ["opening_point", "Opening"], ["autumn", "Autumn"], ["spring", "Spring"],
    ["summer", "Summer"], ["total_pg", "Total PG"], ["total_pl", "Total PL"], ["total", "Total"],
  ];

  return (
    <div className="p-8 max-w-6xl mx-auto">
      <nav className="flex items-center gap-2 text-xs text-slate-400 mb-2"><span>Pastoral</span><span>/</span><span className="text-brand-600 font-semibold">Points Analysis</span></nav>
      <div className="flex items-start justify-between gap-4 mb-5">
        <div>
          <h1 className="text-2xl font-black text-slate-900 tracking-tight mb-1 flex items-center gap-2"><BarChart3 size={22} className="text-brand-600" /> Points Analysis</h1>
          <p className="text-slate-500 text-sm">Per-student conduct-point breakdown by term, with points gained/lost and net total.</p>
        </div>
        <button onClick={exportCsv} disabled={exporting || rows.length === 0} className="btn-secondary gap-2 shrink-0">{exporting ? <Loader2 size={15} className="animate-spin" /> : <Download size={15} />} Export CSV</button>
      </div>

      <div className="flex flex-wrap gap-3 mb-5">
        <select value={section} onChange={(e) => setSection(e.target.value)} className="input w-auto">
          <option value="">All sections</option>
          {(sections as any[]).map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
        </select>
        <select value={house} onChange={(e) => setHouse(e.target.value)} className="input w-auto">
          <option value="">All houses</option>
          {(houses as any[]).map((h) => <option key={h.id} value={h.name}>{h.name}</option>)}
        </select>
      </div>

      <div className="bg-white rounded-xl border border-slate-200 overflow-x-auto">
        {isLoading ? (
          <div className="py-16 text-center"><Loader2 className="w-5 h-5 animate-spin mx-auto text-slate-400" /></div>
        ) : rows.length === 0 ? (
          <p className="text-sm text-slate-400 py-14 text-center">No students in scope.</p>
        ) : (
          <table className="w-full text-left">
            <thead>
              <tr className="bg-slate-50/80 border-b border-slate-100">
                <th className="px-4 py-3 text-[10px] font-bold uppercase tracking-widest text-slate-500">Student</th>
                <th className="px-4 py-3 text-[10px] font-bold uppercase tracking-widest text-slate-500">House</th>
                {cols.map(([, l]) => <th key={l} className="px-4 py-3 text-[10px] font-bold uppercase tracking-widest text-slate-500 text-right">{l}</th>)}
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-50">
              {(rows as any[]).map((r) => (
                <tr key={r.student_id} className="hover:bg-slate-50/70">
                  <td className="px-4 py-3 text-sm font-semibold text-slate-800">{r.student_name}</td>
                  <td className="px-4 py-3 text-sm text-slate-500">{r.house_name || "—"}</td>
                  {cols.map(([k]) => (
                    <td key={k} className={cn("px-4 py-3 text-sm text-right tabular-nums",
                      k === "total" ? "font-bold text-slate-900" : k === "total_pl" ? "text-red-600" : k === "total_pg" ? "text-emerald-600" : "text-slate-700")}>
                      {r[k] ?? 0}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
