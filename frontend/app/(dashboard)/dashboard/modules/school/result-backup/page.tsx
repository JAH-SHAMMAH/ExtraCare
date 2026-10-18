"use client";

import { useState } from "react";
import { Download, Loader2 } from "lucide-react";
import { toast } from "sonner";
import { downloadCsv } from "@/lib/api";
import { useClasses } from "@/hooks/useSchool";
import { useSessions, useSubTerms, useTerms } from "@/hooks/usePlatform";

export default function ResultBackupPage() {
  const classes = useClasses({ page_size: 100 });
  const terms = useTerms();
  const subs = useSubTerms();
  const sessions = useSessions();
  const [f, setF] = useState({ class_id: "", term_id: "", sub_term_id: "", session_id: "" });
  const [busy, setBusy] = useState(false);
  const set = (k: string, v: string) => setF((o) => ({ ...o, [k]: v }));
  const go = async () => {
    setBusy(true);
    try {
      await downloadCsv("/report-extras/backup", { ...f, session_id: f.session_id || undefined }, "results.csv");
    } catch (e: any) {
      toast.error("Could not build the backup. Check that results are set up for that class and term.");
    } finally { setBusy(false); }
  };
  const sel = (label: string, k: keyof typeof f, items: any[], text: (x: any) => string) => (
    <div><label className="label">{label}</label>
      <select className="input" value={f[k]} onChange={(e) => set(k, e.target.value)} aria-label={label}>
        <option value="">Select…</option>{items.map((x) => <option key={x.id} value={x.id}>{text(x)}</option>)}</select></div>
  );
  return (
    <div className="p-4 sm:p-8 max-w-2xl mx-auto">
      <h1 className="text-2xl font-black text-slate-900 tracking-tight">Result Backup Helper</h1>
      <p className="text-slate-500 text-sm mb-4">Download one class&apos;s results for a term as a spreadsheet to keep offline.</p>
      <div className="bg-white border border-slate-200 rounded-xl p-4 grid sm:grid-cols-2 gap-3">
        {sel("Class", "class_id", (classes.data as any)?.items ?? [], (c) => c.name)}
        {sel("Session (optional)", "session_id", sessions.data ?? [], (s: any) => s.name)}
        {sel("Term", "term_id", terms.data ?? [], (t) => t.name)}
        {sel("Sub-term", "sub_term_id", subs.data ?? [], (t) => t.name)}
        <div className="sm:col-span-2">
          <button onClick={go} disabled={busy || !f.class_id || !f.term_id || !f.sub_term_id} className="btn-primary gap-2">
            {busy ? <Loader2 size={15} className="animate-spin" /> : <Download size={15} />} Download backup
          </button>
        </div>
      </div>
    </div>
  );
}
