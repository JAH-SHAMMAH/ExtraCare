"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Loader2 } from "lucide-react";
import { toast } from "sonner";
import { api, schoolApi } from "@/lib/api";

export default function UnassignedStudentsPage() {
  const qc = useQueryClient();
  const [q, setQ] = useState("");
  const [pick, setPick] = useState<Record<string, string>>({});
  const students = useQuery({ queryKey: ["students-unassigned", q], queryFn: () => api.get("/school/students", { params: { unassigned: true, search: q || undefined, page_size: 100 } }).then((r) => r.data) });
  const classes = useQuery({ queryKey: ["classes-all"], queryFn: () => schoolApi.classes.list({ page_size: 200 }) });
  const classList: any[] = Array.isArray(classes.data) ? classes.data : classes.data?.items ?? [];
  const assign = useMutation({
    mutationFn: ({ id, class_id }: { id: string; class_id: string }) => schoolApi.students.update(id, { class_id }),
    onSuccess: () => { toast.success("Class assigned."); qc.invalidateQueries({ queryKey: ["students-unassigned"] }); },
    onError: () => toast.error("Could not assign."),
  });
  const rows: any[] = students.data?.items ?? [];
  return (
    <div className="p-4 sm:p-8 max-w-4xl mx-auto">
      <h1 className="text-2xl font-black text-slate-900 tracking-tight mb-1">Unassigned Students</h1>
      <p className="text-sm text-slate-500 mb-4">Pupils who have not been put in a class yet.</p>
      <input className="input max-w-xs mb-3" placeholder="Search" value={q} onChange={(e) => setQ(e.target.value)} />
      {students.isLoading ? <Loader2 className="animate-spin text-slate-400 mx-auto my-8" /> : (
        <div className="bg-white border border-slate-200 rounded-xl overflow-x-auto">
          <table className="w-full text-sm">
            <tbody>
              {rows.map((s) => (
                <tr key={s.id} className="border-t first:border-t-0">
                  <td className="p-2 font-semibold">{s.first_name} {s.last_name}</td>
                  <td className="p-2 text-slate-500">{s.admission_number}</td>
                  <td className="p-2">
                    <select className="input" aria-label={`Class for ${s.first_name}`} value={pick[s.id] ?? ""} onChange={(e) => setPick((o) => ({ ...o, [s.id]: e.target.value }))}>
                      <option value="">Choose class…</option>
                      {classList.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
                    </select>
                  </td>
                  <td className="p-2 text-right"><button disabled={!pick[s.id]} onClick={() => assign.mutate({ id: s.id, class_id: pick[s.id] })} className="btn-primary">Assign</button></td>
                </tr>
              ))}
              {!rows.length && <tr><td className="p-6 text-center text-slate-400">Everyone has a class.</td></tr>}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
