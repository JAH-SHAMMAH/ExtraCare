"use client";

import { useState } from "react";
import { useClasses } from "@/hooks/useSchool";
import { useTerms, useSubTerms, useBroadsheet } from "@/hooks/usePlatform";
import { useHasPermission } from "@/components/guards/PermissionGate";
import { BulkPrintTab, CommentGridTab } from "@/components/reports/ReportCardPrint";
import { ReportInsightTab } from "@/components/reports/ReportInsightTab";
import { cn } from "@/lib/utils";
import { Loader2, LayoutGrid, BarChart3 } from "lucide-react";

type Tab = "broadsheet" | "bulk" | "head" | "pc" | "insight";
// adminOnly tabs (School Head Comment, Result Insight) are hidden from teachers,
// matching the API gates (school_admin) — a class teacher sees Broadsheet / Bulk
// Print / PC Comment, scoped server-side to their class.
const TABS: [Tab, string, boolean][] = [
  ["broadsheet", "Result Broadsheet", false],
  ["bulk", "Result Bulk Print", false],
  ["head", "School Head Comment", true],
  ["pc", "PC Teachers Comment", false],
  ["insight", "Result Insight", true],
];

export default function ReportsViewPage() {
  const isAdmin = useHasPermission("school_admin:read");
  const visible = TABS.filter(([, , adminOnly]) => isAdmin || !adminOnly);
  const [tab, setTab] = useState<Tab>("broadsheet");
  return (
    <div className="p-8 max-w-full mx-auto">
      <nav className="flex items-center gap-2 text-xs text-slate-400 mb-2"><span>Secondary School Report</span><span>/</span><span className="text-brand-600 font-semibold">Reports View</span></nav>
      <h1 className="text-2xl font-black text-slate-900 tracking-tight mb-1 flex items-center gap-2"><LayoutGrid size={22} className="text-brand-600" /> Reports View</h1>
      <p className="text-slate-500 text-sm mb-5">Class results built from the Report Entry marks and the cumulative columns.</p>

      <div className="flex flex-wrap gap-1 border-b border-slate-200 mb-6">
        {visible.map(([k, l]) => (
          <button key={k} onClick={() => setTab(k)} className={cn("px-3.5 py-2 text-sm font-semibold border-b-2 -mb-px transition whitespace-nowrap", tab === k ? "border-brand-600 text-brand-700" : "border-transparent text-slate-500 hover:text-slate-700")}>{l}</button>
        ))}
      </div>

      {tab === "broadsheet" ? <Broadsheet /> : tab === "bulk" ? <BulkPrintTab />
        : tab === "head" ? <CommentGridTab kind="head" label="Head Comment" />
        : tab === "pc" ? <CommentGridTab kind="pc" label="PC Comment" />
        : tab === "insight" ? <ReportInsightTab /> : (
        <div className="bg-white rounded-xl border border-dashed border-slate-200 p-12 text-center">
          <BarChart3 size={30} className="mx-auto mb-3 text-slate-300" />
          <p className="text-sm font-semibold text-slate-600">{TABS.find(([k]) => k === tab)?.[1]}</p>
          <p className="text-xs text-slate-400 mt-1">Not yet available — arrives in a later batch of the Secondary Report build-out.</p>
        </div>
      )}
    </div>
  );
}

const GRADE_COLOR: Record<string, string> = {
  "A*": "bg-emerald-100 text-emerald-800", A: "bg-emerald-50 text-emerald-700", "B+": "bg-teal-50 text-teal-700",
  B: "bg-sky-50 text-sky-700", C: "bg-indigo-50 text-indigo-700", D: "bg-amber-50 text-amber-700",
  E: "bg-orange-50 text-orange-700", P: "bg-rose-50 text-rose-700", F: "bg-red-100 text-red-700",
};

function Broadsheet() {
  const classesData: any = useClasses({ page_size: 200 }).data;
  const classes: any[] = classesData?.items ?? classesData ?? [];
  const { data: terms = [] } = useTerms();
  const { data: subs = [] } = useSubTerms();
  const [classId, setClassId] = useState("");
  const [termId, setTermId] = useState("");
  const [subTermId, setSubTermId] = useState("");
  const { data: bs, isLoading } = useBroadsheet({ class_id: classId, term_id: termId, sub_term_id: subTermId });

  const num = (v: any) => (v == null ? "" : Number(v));

  return (
    <div className="space-y-4">
      <div className="bg-white rounded-xl border border-slate-200 p-4 flex flex-wrap items-end gap-3">
        <div><label className="label">Class</label><select value={classId} onChange={(e) => setClassId(e.target.value)} className="input"><option value="">— Select —</option>{classes.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}</select></div>
        <div><label className="label">Term</label><select value={termId} onChange={(e) => setTermId(e.target.value)} className="input"><option value="">— Select —</option>{(terms as any[]).map((t) => <option key={t.id} value={t.id}>{t.name}</option>)}</select></div>
        <div><label className="label">Sub-term</label><select value={subTermId} onChange={(e) => setSubTermId(e.target.value)} className="input"><option value="">— Select —</option>{(subs as any[]).map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}</select></div>
        {bs?.display_cumulative && <span className="text-xs text-slate-400 ml-auto">Column: <b className="text-slate-600">{bs.display_cumulative}</b></span>}
      </div>

      {!classId || !termId || !subTermId ? (
        <div className="bg-white rounded-xl border border-dashed border-slate-200 py-16 text-center text-slate-400"><LayoutGrid size={30} className="mx-auto mb-3 opacity-40" /><p className="text-sm">Choose a class, term and sub-term to build the broadsheet.</p></div>
      ) : isLoading ? (
        <div className="py-16 text-center"><Loader2 className="w-5 h-5 animate-spin mx-auto text-slate-400" /></div>
      ) : !bs || bs.rows.length === 0 ? (
        <p className="text-sm text-slate-400 py-14 text-center bg-white rounded-xl border border-slate-200">No results — enter marks under Report Entry first.</p>
      ) : (
        <>
          <div className="bg-white rounded-xl border border-slate-200 overflow-x-auto">
            <table className="text-left border-collapse">
              <thead>
                <tr className="bg-slate-50/80 border-b border-slate-100">
                  <th className="px-3 py-3 text-[10px] font-bold uppercase tracking-widest text-slate-500 sticky left-0 bg-slate-50">#</th>
                  <th className="px-3 py-3 text-[10px] font-bold uppercase tracking-widest text-slate-500 sticky left-8 bg-slate-50 min-w-[160px]">Student</th>
                  {bs.subjects.map((s: any) => <th key={s.id} className="px-2 py-3 text-[9px] font-bold uppercase tracking-wide text-slate-500 text-center min-w-[54px] max-w-[70px]"><div className="leading-tight">{s.name}</div></th>)}
                  {["Total", "Avg", "Grade", "Pos"].map((h) => <th key={h} className="px-3 py-3 text-[10px] font-bold uppercase tracking-widest text-slate-500 text-center bg-slate-100/60">{h}</th>)}
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-50">
                {bs.rows.map((r: any) => (
                  <tr key={r.student_id} className="hover:bg-slate-50/70">
                    <td className="px-3 py-2 text-xs text-slate-400 sticky left-0 bg-white">{r.position}</td>
                    <td className="px-3 py-2 text-sm font-semibold text-slate-800 whitespace-nowrap sticky left-8 bg-white">{r.student_name}</td>
                    {bs.subjects.map((s: any) => { const cell = r.subjects[s.id]; return (
                      <td key={s.id} className={cn("px-2 py-2 text-center text-sm tabular-nums", cell?.grade ? GRADE_COLOR[cell.grade] : "text-slate-300")}>{cell?.value != null ? num(cell.value) : "–"}</td>
                    ); })}
                    <td className="px-3 py-2 text-center text-sm font-bold text-slate-900 tabular-nums bg-slate-50/60">{num(r.total)}</td>
                    <td className="px-3 py-2 text-center text-sm text-slate-700 tabular-nums bg-slate-50/60">{num(r.average)}</td>
                    <td className="px-3 py-2 text-center bg-slate-50/60"><span className={cn("badge", r.grade ? GRADE_COLOR[r.grade] : "")}>{r.grade || "–"}</span></td>
                    <td className="px-3 py-2 text-center text-sm font-semibold text-slate-700 bg-slate-50/60">{r.position}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {bs.bands.length > 0 && (
            <div className="bg-white rounded-xl border border-slate-200 p-4">
              <p className="text-xs font-bold uppercase tracking-widest text-slate-500 mb-2">Grading Scale</p>
              <div className="flex flex-wrap gap-2">
                {bs.bands.map((b: any) => (
                  <span key={b.grade} className={cn("badge", GRADE_COLOR[b.grade] || "bg-slate-50 text-slate-600")}>
                    {b.grade} {b.min_score != null ? `(${num(b.min_score)}–${num(b.max_score)})` : ""}{b.remark ? ` · ${b.remark}` : ""}
                  </span>
                ))}
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}
