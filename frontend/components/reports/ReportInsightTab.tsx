"use client";

import { useState } from "react";
import { useTerms, useSubTerms, useReportInsight } from "@/hooks/usePlatform";
import { cn } from "@/lib/utils";
import { Loader2, BarChart3 } from "lucide-react";
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Legend, CartesianGrid } from "recharts";

type Sub = "gender" | "subject" | "class";
const SUBS: [Sub, string][] = [["gender", "Gender performance"], ["subject", "Subject performance"], ["class", "Class performance"]];

export function ReportInsightTab() {
  const { data: terms = [] } = useTerms();
  const { data: subs = [] } = useSubTerms();
  const [termId, setTermId] = useState("");
  const [subTermId, setSubTermId] = useState("");
  const [chart, setChart] = useState<Sub>("gender");
  const { data: ins, isLoading } = useReportInsight({ term_id: termId, sub_term_id: subTermId });

  const genderData = (ins?.gender ?? []).map((g: any) => ({ name: g.subject_name, Male: Number(g.male ?? 0), Female: Number(g.female ?? 0) }));
  const subjectData = (ins?.subjects ?? []).map((s: any) => ({ name: s.subject_name, Average: Number(s.average ?? 0) }));
  const classData = (ins?.classes ?? []).map((c: any) => ({ name: c.class_name, Average: Number(c.average ?? 0) }));

  return (
    <div className="space-y-4">
      <div className="bg-white rounded-xl border border-slate-200 p-4 flex flex-wrap items-end gap-3">
        <div><label className="label">Term</label><select value={termId} onChange={(e) => setTermId(e.target.value)} className="input"><option value="">— Select —</option>{(terms as any[]).map((t) => <option key={t.id} value={t.id}>{t.name}</option>)}</select></div>
        <div><label className="label">Sub-term</label><select value={subTermId} onChange={(e) => setSubTermId(e.target.value)} className="input"><option value="">— Select —</option>{(subs as any[]).map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}</select></div>
        <div className="inline-flex gap-1 bg-slate-100 rounded-lg p-1 ml-auto">
          {SUBS.map(([k, l]) => <button key={k} onClick={() => setChart(k)} className={cn("px-3 py-1.5 text-xs font-semibold rounded-md transition", chart === k ? "bg-white text-brand-700 shadow-sm" : "text-slate-500 hover:text-slate-700")}>{l}</button>)}
        </div>
      </div>

      {!termId || !subTermId ? (
        <div className="bg-white rounded-xl border border-dashed border-slate-200 py-16 text-center text-slate-400"><BarChart3 size={30} className="mx-auto mb-3 opacity-40" /><p className="text-sm">Choose a term and sub-term to see performance charts.</p></div>
      ) : isLoading ? (
        <div className="py-16 text-center"><Loader2 className="w-5 h-5 animate-spin mx-auto text-slate-400" /></div>
      ) : !ins || (chart === "gender" ? genderData : chart === "subject" ? subjectData : classData).length === 0 ? (
        <p className="text-sm text-slate-400 py-14 text-center bg-white rounded-xl border border-slate-200">No results to display — enter marks under Report Entry first.</p>
      ) : (
        <div className="bg-white rounded-xl border border-slate-200 p-5">
          <h3 className="text-sm font-bold text-slate-800 mb-4">{SUBS.find(([k]) => k === chart)?.[1]} · {ins.term_name} {ins.sub_term_name}</h3>
          <div style={{ width: "100%", height: 420 }}>
            <ResponsiveContainer>
              {chart === "gender" ? (
                <BarChart data={genderData} margin={{ bottom: 60 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
                  <XAxis dataKey="name" angle={-40} textAnchor="end" interval={0} tick={{ fontSize: 11 }} height={70} />
                  <YAxis domain={[0, 100]} label={{ value: "Ave Score (%)", angle: -90, position: "insideLeft", style: { fontSize: 11 } }} />
                  <Tooltip /><Legend />
                  <Bar dataKey="Male" fill="#0f766e" /><Bar dataKey="Female" fill="#f59e0b" />
                </BarChart>
              ) : (
                <BarChart data={chart === "subject" ? subjectData : classData} margin={{ bottom: 60 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
                  <XAxis dataKey="name" angle={-40} textAnchor="end" interval={0} tick={{ fontSize: 11 }} height={70} />
                  <YAxis domain={[0, 100]} label={{ value: "Average (%)", angle: -90, position: "insideLeft", style: { fontSize: 11 } }} />
                  <Tooltip />
                  <Bar dataKey="Average" fill="#0f766e" />
                </BarChart>
              )}
            </ResponsiveContainer>
          </div>
        </div>
      )}
    </div>
  );
}
