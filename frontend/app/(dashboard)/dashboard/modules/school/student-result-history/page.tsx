"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Loader2, Printer } from "lucide-react";
import { reportExtrasApi } from "@/lib/api";
import { useStudents } from "@/hooks/useSchool";

export default function StudentResultHistoryPage() {
  const [q, setQ] = useState("");
  const [id, setId] = useState("");
  const students = useStudents({ search: q || undefined, page_size: 20 });
  const hist = useQuery({ queryKey: ["result-history", id], queryFn: () => reportExtrasApi.history(id), enabled: !!id, retry: false });
  const list: any[] = (students.data as any)?.items ?? [];
  return (
    <div className="p-4 sm:p-8 max-w-4xl mx-auto">
      <h1 className="text-2xl font-black text-slate-900 tracking-tight">Student Result History</h1>
      <p className="text-slate-500 text-sm mb-4 print:hidden">Every term&apos;s result for one pupil, oldest first.</p>
      <div className="flex flex-wrap gap-2 mb-4 print:hidden">
        <input className="input max-w-xs" placeholder="Search pupil" value={q} onChange={(e) => setQ(e.target.value)} />
        <select className="input max-w-xs" aria-label="Pupil" value={id} onChange={(e) => setId(e.target.value)}>
          <option value="">Select pupil…</option>
          {list.map((s) => <option key={s.id} value={s.id}>{s.first_name} {s.last_name} ({s.student_id})</option>)}
        </select>
        {hist.data && <button onClick={() => window.print()} className="btn-secondary gap-1"><Printer size={15} /> Print</button>}
      </div>
      {hist.isLoading && id && <Loader2 className="animate-spin text-slate-400 mx-auto my-8" />}
      {hist.isError && <p className="text-sm text-red-600">Could not load this pupil&apos;s history.</p>}
      {hist.data && (
        <div className="bg-white border border-slate-200 rounded-xl overflow-x-auto">
          <div className="px-4 py-3 font-bold bg-slate-50">{hist.data.student.name} · {hist.data.student.admission_no}</div>
          <table className="w-full text-sm min-w-[560px]">
            <thead><tr className="text-left text-xs uppercase text-slate-500"><th className="p-2">Session</th><th className="p-2">Term</th><th className="p-2">Sub-term</th><th className="p-2">Class</th><th className="p-2">Average</th><th className="p-2">Grade</th><th className="p-2">Position</th></tr></thead>
            <tbody>
              {hist.data.items.map((r, i) => (
                <tr key={i} className="border-t"><td className="p-2">{r.session}</td><td className="p-2">{r.term}</td><td className="p-2">{r.sub_term}</td><td className="p-2">{r.class_name}</td>
                  <td className="p-2 font-semibold">{r.average.toFixed(1)}%</td><td className="p-2">{r.grade ?? "—"}</td><td className="p-2">{r.position} / {r.class_size}</td></tr>
              ))}
              {!hist.data.items.length && <tr><td colSpan={7} className="p-6 text-center text-slate-400">No results found for this pupil yet.</td></tr>}
            </tbody>
          </table>
          {hist.data.hidden > 0 && <p className="text-xs text-slate-400 p-3">{hist.data.hidden} term(s) left out because they are not published or not set up for this pupil.</p>}
        </div>
      )}
    </div>
  );
}
