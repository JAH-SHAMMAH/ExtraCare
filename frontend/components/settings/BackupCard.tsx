"use client";

import { useState } from "react";
import { Database, Download } from "lucide-react";
import { backupApi } from "@/lib/api";

async function reason(err: any): Promise<string> {
  const data = err?.response?.data;
  try {
    const text = data instanceof Blob ? await data.text() : JSON.stringify(data ?? {});
    return JSON.parse(text).detail || "The backup could not be downloaded.";
  } catch {
    return "The backup could not be downloaded.";
  }
}

export default function BackupCard() {
  const [open, setOpen] = useState(false);
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [done, setDone] = useState(false);

  async function go() {
    setBusy(true); setError(""); setDone(false);
    try {
      const blob = await backupApi.download(password);
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `fairview-backup-${new Date().toISOString().slice(0, 10)}.logical.jsonl.gz`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
      setDone(true); setPassword(""); setOpen(false);
    } catch (e) {
      setError(await reason(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="bg-white rounded-xl border border-slate-200 p-6">
      <h2 className="text-sm font-bold text-slate-800 mb-2 flex items-center gap-2">
        <Database size={15} /> Database backup
      </h2>
      <p className="text-xs text-slate-500 mb-4">
        Download a copy of everything in the portal (students, staff, results, fees). Keep the file somewhere safe and private.
      </p>
      {!open ? (
        <button onClick={() => { setOpen(true); setDone(false); }}
          className="px-4 py-2 rounded-lg text-sm font-medium text-white bg-brand-600 hover:bg-brand-700 flex items-center gap-2">
          <Download size={14} /> Download backup
        </button>
      ) : (
        <div className="space-y-3 max-w-sm">
          <label className="label" htmlFor="backup-pw">Enter your password to continue</label>
          <input id="backup-pw" type="password" autoComplete="current-password" className="input"
            value={password} onChange={(e) => setPassword(e.target.value)} />
          <div className="flex gap-2">
            <button onClick={go} disabled={busy || !password}
              className="px-4 py-2 rounded-lg text-sm font-medium text-white bg-brand-600 hover:bg-brand-700 disabled:opacity-50">
              {busy ? "Preparing…" : "Download"}
            </button>
            <button onClick={() => { setOpen(false); setPassword(""); setError(""); }}
              className="px-4 py-2 rounded-lg text-sm font-medium border border-slate-200 text-slate-600">Cancel</button>
          </div>
        </div>
      )}
      {error && <p role="alert" className="text-xs text-red-600 mt-3">{error}</p>}
      {done && <p className="text-xs text-emerald-700 mt-3">Backup downloaded.</p>}
    </div>
  );
}
