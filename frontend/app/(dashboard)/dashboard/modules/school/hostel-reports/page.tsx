"use client";

import { useState } from "react";
import { useHostels, useHostelReports, useAddHostelReport, useDeleteHostelReport } from "@/hooks/usePastoral";
import { useHasPermission } from "@/components/guards/PermissionGate";
import { cn } from "@/lib/utils";
import { Loader2, FileText, Trash2, Plus } from "lucide-react";

type RType = "daily" | "manager";

export default function HostelReportsPage() {
  const canWrite = useHasPermission("school:hostel:write");
  const [rtype, setRtype] = useState<RType>("daily");
  const { data: hostelData } = useHostels();
  const hostels = hostelData?.items ?? [];
  const { data: reports = [], isLoading } = useHostelReports({ report_type: rtype });
  const add = useAddHostelReport();
  const del = useDeleteHostelReport();
  const [show, setShow] = useState(false);
  const [f, setF] = useState({ hostel_id: "", report_date: "", title: "", body: "" });

  const reset = () => { setF({ hostel_id: "", report_date: "", title: "", body: "" }); setShow(false); };
  const submit = () => {
    if (!f.hostel_id) return;
    add.mutate(
      { report_type: rtype, hostel_id: f.hostel_id, report_date: f.report_date || null, title: f.title || null, body: f.body || null },
      { onSuccess: reset },
    );
  };

  return (
    <div className="p-8 max-w-5xl mx-auto">
      <nav className="flex items-center gap-2 text-xs text-slate-400 mb-2"><span>Pastoral</span><span>/</span><span className="text-brand-600 font-semibold">Hostel Reports</span></nav>
      <div className="flex items-start justify-between gap-4 mb-5">
        <div>
          <h1 className="text-2xl font-black text-slate-900 tracking-tight mb-1 flex items-center gap-2"><FileText size={22} className="text-brand-600" /> Hostel Reports</h1>
          <p className="text-slate-500 text-sm">Daily roll/notes and periodic manager summaries per hostel.</p>
        </div>
        {canWrite && <button onClick={() => setShow((s) => !s)} className="btn-primary gap-2 shrink-0"><Plus size={15} /> New Report</button>}
      </div>

      <div className="inline-flex gap-1 bg-slate-100 rounded-lg p-1 mb-6">
        {([["daily", "Daily Reports"], ["manager", "Manager Reports"]] as [RType, string][]).map(([k, l]) => (
          <button key={k} onClick={() => setRtype(k)} className={cn("px-3.5 py-1.5 text-sm font-semibold rounded-md transition", rtype === k ? "bg-white text-brand-700 shadow-sm" : "text-slate-500 hover:text-slate-700")}>{l}</button>
        ))}
      </div>

      {show && canWrite && (
        <div className="bg-white rounded-xl border border-slate-200 p-6 mb-6 grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <label className="label">Hostel *</label>
            <select value={f.hostel_id} onChange={(e) => setF({ ...f, hostel_id: e.target.value })} className="input">
              <option value="">— Select —</option>
              {(hostels as any[]).map((h) => <option key={h.id} value={h.id}>{h.name}</option>)}
            </select>
          </div>
          <div><label className="label">Date</label><input type="date" value={f.report_date} onChange={(e) => setF({ ...f, report_date: e.target.value })} className="input" /></div>
          <div className="md:col-span-2"><label className="label">Title</label><input value={f.title} onChange={(e) => setF({ ...f, title: e.target.value })} className="input" placeholder={rtype === "daily" ? "e.g. Evening roll" : "e.g. Weekly summary"} /></div>
          <div className="md:col-span-2"><label className="label">Body</label><textarea value={f.body} onChange={(e) => setF({ ...f, body: e.target.value })} className="input" rows={4} /></div>
          <div className="md:col-span-2 flex justify-end gap-3"><button onClick={reset} className="btn-secondary">Cancel</button><button onClick={submit} disabled={!f.hostel_id || add.isPending} className="btn-primary gap-2">{add.isPending && <Loader2 size={15} className="animate-spin" />} Save</button></div>
        </div>
      )}

      {isLoading ? (
        <div className="py-16 text-center"><Loader2 className="w-5 h-5 animate-spin mx-auto text-slate-400" /></div>
      ) : (reports as any[]).length === 0 ? (
        <div className="bg-white rounded-xl border border-slate-200 py-14 text-center text-slate-400"><FileText size={30} className="mx-auto mb-3 opacity-40" /><p className="text-sm">No {rtype} reports yet.</p></div>
      ) : (
        <div className="space-y-3">
          {(reports as any[]).map((r) => (
            <div key={r.id} className="bg-white rounded-xl border border-slate-200 p-5">
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <h3 className="text-sm font-bold text-slate-900">{r.title || "(untitled)"}</h3>
                  <p className="text-xs text-slate-400 mt-0.5">{[r.hostel_name, r.report_date, r.recorded_by_name].filter(Boolean).join(" · ")}</p>
                </div>
                {canWrite && <button onClick={() => { if (confirm("Delete this report?")) del.mutate(r.id); }} className="text-slate-400 hover:text-red-600 p-1 shrink-0"><Trash2 size={15} /></button>}
              </div>
              {r.body && <p className="text-sm text-slate-600 mt-3 whitespace-pre-wrap">{r.body}</p>}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
