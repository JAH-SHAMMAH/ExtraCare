"use client";

import { useState } from "react";
import Link from "next/link";
import { schoolApi } from "@/lib/api";
import { parseTeacherLines, type BulkRow } from "@/lib/teacherBulk";
import { cn } from "@/lib/utils";
import { toast } from "sonner";
import { ArrowLeft, Loader2, Copy, Download, KeyRound, CheckCircle2, AlertTriangle } from "lucide-react";

// First-run convenience: the four teachers being onboarded. Clear it to paste your own.
const STARTER = [
  "Mr Jeremiah CRS, secondary",
  "Ms Chiamaka Biology, secondary",
  "Mrs Juliet French, primary",
  "Mr Isaiah ICT, primary",
].join("\n");

interface Result {
  index: number; name: string; email: string; subject?: string; department?: string;
  sections: string[]; status: "ok" | "conflict" | "error"; message: string;
  id?: string; temporary_password?: string;
}

const payload = (rows: BulkRow[]) => rows.map((r) => ({
  title: r.title || null, first_name: r.first_name, last_name: r.last_name || "",
  subject: r.subject || null, department: r.department || null, email: r.email || null,
}));

export default function BulkTeachersPage() {
  const [text, setText] = useState(STARTER);
  const [rows, setRows] = useState<BulkRow[]>([]);
  const [results, setResults] = useState<Result[] | null>(null);
  const [created, setCreated] = useState(false);
  const [busy, setBusy] = useState(false);

  const call = async (dry: boolean, list: BulkRow[]) => {
    setBusy(true);
    try {
      const res = await schoolApi.teachers.bulkCreate({ rows: payload(list), dry_run: dry });
      setResults(res.rows);
      return res;
    } catch (e: any) {
      toast.error(e?.response?.data?.detail?.toString?.() || "Request failed.");
      return null;
    } finally { setBusy(false); }
  };

  const preview = async () => {
    const parsed = parseTeacherLines(text);
    if (!parsed.length) { toast.error("Paste at least one teacher."); return; }
    setRows(parsed); setCreated(false);
    await call(true, parsed);
  };

  const edit = (i: number, k: keyof BulkRow, v: string) =>
    setRows((rs) => rs.map((r, j) => (j === i ? { ...r, [k]: v } : r)));

  const create = async () => {
    const res = await call(false, rows);
    if (res) { setCreated(true); toast.success(`${res.created} account(s) created.`); }
  };

  const okCount = results?.filter((r) => r.status === "ok").length ?? 0;
  const withPw = results?.filter((r) => r.temporary_password) ?? [];

  const sheet = () => withPw.map((r) => `${r.name} | ${r.email} | ${r.temporary_password}`).join("\n");
  const copy = async () => {
    try { await navigator.clipboard.writeText(sheet()); toast.success("Copied."); } catch { toast.error("Copy failed."); }
  };
  const download = () => {
    const csv = "Name,Email,Temporary password\n" + withPw.map((r) => `"${r.name}",${r.email},${r.temporary_password}`).join("\n");
    const a = document.createElement("a");
    a.href = URL.createObjectURL(new Blob([csv], { type: "text/csv" }));
    a.download = "new-teacher-logins.csv"; a.click(); URL.revokeObjectURL(a.href);
  };

  return (
    <div className="p-8 max-w-5xl mx-auto">
      <Link href="/dashboard/modules/school/teachers" className="inline-flex items-center gap-1.5 text-xs text-slate-500 hover:text-slate-700 mb-2"><ArrowLeft size={13} /> View Teachers</Link>
      <h1 className="text-2xl font-black text-slate-900 tracking-tight mb-1">Bulk Add Teachers</h1>
      <p className="text-sm text-slate-500 mb-5">
        One teacher per line: title, first name, subject, then department. Emails become
        <span className="font-semibold"> firstname@your-school-domain</span>. Each teacher gets a temporary password and must choose their own at first sign-in.
      </p>

      {!created && (
        <div className="bg-white rounded-xl border border-slate-200 p-5 mb-5">
          <label className="text-sm font-semibold text-slate-600">Teachers</label>
          <textarea value={text} onChange={(e) => setText(e.target.value)} rows={6} className="input w-full mt-1 font-mono text-sm" placeholder={"Mr Jeremiah CRS, secondary\nMrs Juliet French, primary"} />
          <button onClick={preview} disabled={busy} className="btn-primary gap-2 mt-3">{busy && <Loader2 size={15} className="animate-spin" />}Preview</button>
        </div>
      )}

      {results && !created && rows.length > 0 && (
        <div className="bg-white rounded-xl border border-slate-200 overflow-x-auto mb-5">
          <table className="w-full text-sm">
            <thead className="bg-slate-50 text-xs uppercase text-slate-500">
              <tr>{["Title", "First name", "Subject", "Department", "Email", "Sections", ""].map((h) => <th key={h} className="px-3 py-2 text-left">{h}</th>)}</tr>
            </thead>
            <tbody>
              {rows.map((r, i) => {
                const res = results[i];
                return (
                  <tr key={i} className="border-t border-slate-100 align-top">
                    <td className="px-3 py-2"><input className="input w-16" value={r.title} onChange={(e) => edit(i, "title", e.target.value)} /></td>
                    <td className="px-3 py-2"><input className="input w-32" value={r.first_name} onChange={(e) => edit(i, "first_name", e.target.value)} /></td>
                    <td className="px-3 py-2"><input className="input w-28" value={r.subject} onChange={(e) => edit(i, "subject", e.target.value)} /></td>
                    <td className="px-3 py-2"><input className="input w-28" value={r.department} onChange={(e) => edit(i, "department", e.target.value)} /></td>
                    <td className="px-3 py-2"><input className="input w-56" value={r.email || res?.email || ""} onChange={(e) => edit(i, "email", e.target.value)} /></td>
                    <td className="px-3 py-2 text-slate-600">{res?.sections?.join(", ") || "—"}</td>
                    <td className="px-3 py-2">
                      {res && (res.status === "ok"
                        ? <span className="inline-flex items-center gap-1 text-emerald-700 text-xs font-semibold"><CheckCircle2 size={14} /> Ready</span>
                        : <span className="inline-flex items-start gap-1 text-amber-700 text-xs max-w-[220px]"><AlertTriangle size={14} className="shrink-0 mt-0.5" /> {res.message}</span>)}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
          <div className="flex items-center gap-3 px-4 py-3 border-t border-slate-100 bg-slate-50/60">
            <button onClick={() => call(true, rows)} disabled={busy} className="btn-secondary py-1.5">Re-check</button>
            <button onClick={create} disabled={busy || okCount === 0} className={cn("btn-primary gap-2 py-1.5", okCount === 0 && "opacity-50")}>
              {busy && <Loader2 size={15} className="animate-spin" />}Create {okCount} account{okCount === 1 ? "" : "s"}
            </button>
            <span className="text-xs text-slate-500">Rows with a warning are skipped.</span>
          </div>
        </div>
      )}

      {created && results && (
        <div className="bg-white rounded-xl border border-emerald-200 p-5">
          <h2 className="font-bold text-slate-900 flex items-center gap-2 mb-1"><KeyRound size={18} className="text-emerald-600" /> Logins created</h2>
          <p className="text-sm text-amber-700 bg-amber-50 border border-amber-200 rounded-lg px-3 py-2 mb-4">
            These temporary passwords are shown <b>once</b>. Copy or download them now and hand them over privately. Each teacher will be asked to set a new password when they first sign in.
          </p>
          <table className="w-full text-sm mb-4">
            <thead className="text-xs uppercase text-slate-500"><tr><th className="text-left py-1">Name</th><th className="text-left">Email</th><th className="text-left">Temporary password</th></tr></thead>
            <tbody>
              {results.map((r) => (
                <tr key={r.index} className="border-t border-slate-100">
                  <td className="py-2">{r.name}</td><td>{r.email}</td>
                  <td className="font-mono">{r.temporary_password ?? <span className="text-amber-700 font-sans text-xs">Skipped — {r.message}</span>}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <div className="flex gap-2">
            <button onClick={copy} className="btn-secondary gap-1.5 py-1.5"><Copy size={14} /> Copy all</button>
            <button onClick={download} className="btn-secondary gap-1.5 py-1.5"><Download size={14} /> Download CSV</button>
            <Link href="/dashboard/modules/school/teachers" className="btn-primary py-1.5">Done</Link>
          </div>
        </div>
      )}
    </div>
  );
}
