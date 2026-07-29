"use client";

import { useRef, useState } from "react";
import { useHostels, useHostelStudents, useImportHostelStudents } from "@/hooks/usePastoral";
import { useHasPermission } from "@/components/guards/PermissionGate";
import { pastoralApi } from "@/lib/api";
import { Loader2, BedDouble, Download, Upload } from "lucide-react";
import { toast } from "sonner";

export default function HostelStudentsPage() {
  const canWrite = useHasPermission("school:hostel:write");
  const [hostelId, setHostelId] = useState("");
  const [search, setSearch] = useState("");
  const params = { hostel_id: hostelId || undefined, search: search || undefined };
  const { data: hostelData } = useHostels();
  const { data: rows = [], isLoading } = useHostelStudents(params);
  const doImport = useImportHostelStudents();
  const fileRef = useRef<HTMLInputElement>(null);
  const [exporting, setExporting] = useState(false);

  const onImport = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const fd = new FormData();
    fd.append("file", file);
    doImport.mutate(fd);
    if (fileRef.current) fileRef.current.value = "";
  };

  const exportCsv = async () => {
    setExporting(true);
    try {
      const blob = await pastoralApi.hostelStudents.exportCsv(params);
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url; a.download = "hostel-students.csv"; a.click();
      URL.revokeObjectURL(url);
    } catch { toast.error("Export failed."); } finally { setExporting(false); }
  };

  const hostels = hostelData?.items ?? [];

  return (
    <div className="p-8 max-w-6xl mx-auto">
      <nav className="flex items-center gap-2 text-xs text-slate-400 mb-2"><span>Pastoral</span><span>/</span><span className="text-brand-600 font-semibold">Hostel Students</span></nav>
      <div className="flex items-start justify-between gap-4 mb-5">
        <div>
          <h1 className="text-2xl font-black text-slate-900 tracking-tight mb-1 flex items-center gap-2"><BedDouble size={22} className="text-brand-600" /> Hostel Students</h1>
          <p className="text-slate-500 text-sm">All boarders and their bed allocations. Import to bulk-allocate from a spreadsheet.</p>
        </div>
        <div className="flex gap-2 shrink-0">
          {canWrite && (
            <>
              <input ref={fileRef} type="file" accept=".csv,.xlsx,.xls,.docx,.pdf" onChange={onImport} className="hidden" />
              <button onClick={() => fileRef.current?.click()} disabled={doImport.isPending} className="btn-secondary gap-2">{doImport.isPending ? <Loader2 size={15} className="animate-spin" /> : <Upload size={15} />} Import</button>
            </>
          )}
          <button onClick={exportCsv} disabled={exporting || rows.length === 0} className="btn-secondary gap-2">{exporting ? <Loader2 size={15} className="animate-spin" /> : <Download size={15} />} Export</button>
        </div>
      </div>

      <div className="flex flex-wrap gap-3 mb-5">
        <select value={hostelId} onChange={(e) => setHostelId(e.target.value)} className="input w-auto">
          <option value="">All hostels</option>
          {(hostels as any[]).map((h) => <option key={h.id} value={h.id}>{h.name}</option>)}
        </select>
        <input value={search} onChange={(e) => setSearch(e.target.value)} className="input w-auto" placeholder="Search name / ID…" />
      </div>

      <p className="text-xs text-slate-400 mb-2">Import columns (case-insensitive): <code>student</code> (name) or <code>admission_no</code>, <code>hostel</code> (name), <code>room</code>, <code>bed</code>. Accepts CSV, Excel, Word or PDF (with a table).</p>

      <div className="bg-white rounded-xl border border-slate-200 overflow-x-auto">
        {isLoading ? (
          <div className="py-16 text-center"><Loader2 className="w-5 h-5 animate-spin mx-auto text-slate-400" /></div>
        ) : rows.length === 0 ? (
          <p className="text-sm text-slate-400 py-14 text-center">No boarders allocated.</p>
        ) : (
          <table className="w-full text-left">
            <thead><tr className="bg-slate-50/80 border-b border-slate-100">{["Student", "Admission No", "Hostel", "Room", "Bed"].map((h) => <th key={h} className="px-4 py-3 text-[10px] font-bold uppercase tracking-widest text-slate-500">{h}</th>)}</tr></thead>
            <tbody className="divide-y divide-slate-50">
              {(rows as any[]).map((r) => (
                <tr key={r.allocation_id} className="hover:bg-slate-50/70">
                  <td className="px-4 py-3 text-sm font-semibold text-slate-800">{r.student_name}</td>
                  <td className="px-4 py-3 text-sm text-slate-500">{r.admission_no || "—"}</td>
                  <td className="px-4 py-3 text-sm text-slate-600">{r.hostel_name || "—"}</td>
                  <td className="px-4 py-3 text-sm text-slate-600">{r.room || "—"}</td>
                  <td className="px-4 py-3 text-sm text-slate-600">{r.bed || "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
