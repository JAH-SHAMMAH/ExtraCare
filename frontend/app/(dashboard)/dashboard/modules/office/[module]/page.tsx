"use client";

import { useParams } from "next/navigation";
import { useState } from "react";
import { Download, Loader2, Lock, Pencil, Plus, Printer, RefreshCw, Trash2, X } from "lucide-react";
import { useQueryClient } from "@tanstack/react-query";
import { api, downloadCsv } from "@/lib/api";
import { toast } from "sonner";
import { useOfficeDelete, useOfficeRows, useOfficeSave, useOfficeSchema, useOfficeSummary } from "@/hooks/useOffice";
import { cn } from "@/lib/utils";

const title = (s: string) => s.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
const money = (n: any) => Number(n ?? 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const MONEY_COLS = new Set(["price", "total", "amount", "rate", "cost", "float_amount", "debit", "credit", "balance", "outstanding", "paid", "raised"]);
type Cols = Record<string, { kind: string; required: boolean }>;

function Summary({ module }: { module: string }) {
  const { data } = useOfficeSummary(module);
  if (!data) return null;
  const scalars = Object.entries(data).filter(([, v]) => typeof v !== "object");
  const tables = Object.entries(data).filter(([, v]) => Array.isArray(v) && (v as any[]).length && typeof (v as any[])[0] === "object");
  return (
    <div className="mb-5 space-y-3">
      {!!scalars.length && (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          {scalars.map(([k, v]) => (
            <div key={k} className="bg-white border border-slate-200 rounded-xl p-3">
              <div className="text-xs text-slate-500">{title(k)}</div>
              <div className="text-xl font-black text-slate-900">{MONEY_COLS.has(k) || /revenue|raised|spend|income|unpaid|value|outstanding/.test(k) ? money(v) : String(v)}</div>
            </div>
          ))}
        </div>
      )}
      {tables.map(([k, rows]) => {
        const cols = Object.keys((rows as any[])[0]).filter((c) => c !== "id");
        return (
          <div key={k} className="bg-white border border-slate-200 rounded-xl overflow-x-auto">
            <div className="px-3 py-2 font-bold text-sm bg-slate-50">{title(k)}</div>
            <table className="w-full text-sm"><thead><tr className="text-left text-xs uppercase text-slate-500">{cols.map((c) => <th key={c} className="p-2">{title(c)}</th>)}</tr></thead>
              <tbody>{(rows as any[]).map((r, i) => <tr key={r.id ?? i} className="border-t">{cols.map((c) => <td key={c} className="p-2">{MONEY_COLS.has(c) ? money(r[c]) : String(r[c] ?? "")}</td>)}</tr>)}</tbody></table>
          </div>
        );
      })}
    </div>
  );
}

function LinesEditor({ value, onChange, kind, accounts }: { value: any[]; onChange: (v: any[]) => void; kind: "items" | "lines"; accounts: any[] }) {
  const set = (i: number, p: object) => onChange(value.map((x, j) => (j === i ? { ...x, ...p } : x)));
  return (
    <div className="space-y-2">
      {value.map((ln, i) => (
        <div key={i} className="flex flex-wrap gap-2 items-center">
          {kind === "items" ? (
            <>
              <input className="input flex-1 min-w-[120px]" placeholder="Item" aria-label={`Item ${i + 1} name`} value={ln.name ?? ""} onChange={(e) => set(i, { name: e.target.value })} />
              <input type="number" min={0} className="input w-20" placeholder="Qty" aria-label={`Item ${i + 1} qty`} value={ln.qty ?? 1} onChange={(e) => set(i, { qty: Number(e.target.value) })} />
              <input type="number" min={0} className="input w-28" placeholder="Price" aria-label={`Item ${i + 1} price`} value={ln.price ?? 0} onChange={(e) => set(i, { price: Number(e.target.value) })} />
            </>
          ) : (
            <>
              <select className="input flex-1 min-w-[140px]" aria-label={`Line ${i + 1} account`} value={ln.account_id ?? ""} onChange={(e) => set(i, { account_id: e.target.value })}>
                <option value="">Account…</option>{accounts.map((a) => <option key={a.id} value={a.id}>{a.code} · {a.name}</option>)}
              </select>
              <input type="number" min={0} className="input w-28" placeholder="Debit" aria-label={`Line ${i + 1} debit`} value={ln.debit ?? ""} onChange={(e) => set(i, { debit: Number(e.target.value), credit: 0 })} />
              <input type="number" min={0} className="input w-28" placeholder="Credit" aria-label={`Line ${i + 1} credit`} value={ln.credit ?? ""} onChange={(e) => set(i, { credit: Number(e.target.value), debit: 0 })} />
            </>
          )}
          <button type="button" onClick={() => onChange(value.filter((_, j) => j !== i))} aria-label={`Remove line ${i + 1}`} className="text-red-500"><X size={16} /></button>
        </div>
      ))}
      <button type="button" onClick={() => onChange([...value, kind === "items" ? { name: "", qty: 1, price: 0 } : { account_id: "", debit: 0, credit: 0 }])} className="btn-secondary gap-1"><Plus size={14} /> Add line</button>
    </div>
  );
}

function RefSelect({ module, resource, value, onChange }: { module: string; resource: string; value: string; onChange: (v: string) => void }) {
  const { data } = useOfficeRows(module, resource);
  return (
    <select className="input" value={value ?? ""} onChange={(e) => onChange(e.target.value)} aria-label={title(resource)}>
      <option value="">Select…</option>
      {(data?.items ?? []).map((r) => <option key={r.id} value={r.id}>{r.name ?? r.tag ?? r.holder ?? r.debtor ?? r.title ?? r.code ?? r.id.slice(0, 6)}</option>)}
    </select>
  );
}

function Form({ module, resource, cols, initial, onDone }: { module: string; resource: string; cols: Cols; initial?: any; onDone: () => void }) {
  const [v, setV] = useState<Record<string, any>>(initial ?? {});
  const save = useOfficeSave(module, resource);
  const accounts = useOfficeRows("ledger", "accounts", undefined);
  const set = (k: string, x: any) => setV((o) => ({ ...o, [k]: x }));
  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    const body: Record<string, any> = {};
    Object.keys(cols).forEach((c) => { if (c !== "total" && v[c] !== undefined && v[c] !== "") body[c] = v[c]; });
    save.mutate({ id: initial?.id, body }, {
      onSuccess: () => { toast.success("Saved."); onDone(); },
      onError: (err: any) => toast.error(typeof err?.response?.data?.detail === "string" ? err.response.data.detail : "Could not save."),
    });
  };
  return (
    <form onSubmit={submit} className="bg-slate-50 border border-slate-200 rounded-xl p-4 mb-4 grid sm:grid-cols-2 gap-3">
      {Object.entries(cols).filter(([c]) => !["total", "approved_by", "requested_by", "approvals", "awaiting"].includes(c)).map(([c, m]) => (
        <div key={c} className={cn(m.kind === "json" || m.kind === "text" ? "sm:col-span-2" : "")}>
          <label className="label">{title(c.replace(/_id$/, ""))}{m.required && " *"}</label>
          {m.kind === "json" ? <LinesEditor kind={c === "lines" ? "lines" : "items"} value={v[c] ?? []} onChange={(x) => set(c, x)} accounts={accounts.data?.items ?? []} />
            : m.kind === "text" ? <textarea className="input" rows={2} value={v[c] ?? ""} onChange={(e) => set(c, e.target.value)} />
            : m.kind === "bool" ? <input type="checkbox" className="h-5 w-5 accent-emerald-600" checked={v[c] ?? (c !== "paid")} onChange={(e) => set(c, e.target.checked)} aria-label={title(c)} />
            : m.kind === "date" ? <input type="date" className="input" value={v[c] ?? ""} onChange={(e) => set(c, e.target.value)} />
            : m.kind === "float" || m.kind === "int" ? <input type="number" min={0} step={m.kind === "float" ? "0.01" : "1"} className="input" value={v[c] ?? ""} onChange={(e) => set(c, e.target.value)} />
            : m.kind.startsWith("choice:") ? (
              <select className="input" value={v[c] ?? ""} onChange={(e) => set(c, e.target.value)}>
                <option value="">{m.required ? "Select…" : "Default"}</option>
                {m.kind.split(":")[1].split("|").map((o) => <option key={o} value={o}>{title(o)}</option>)}
              </select>
            )
            : m.kind.startsWith("ref:") ? <RefSelect module={module} resource={m.kind.split(":")[1]} value={v[c]} onChange={(x) => set(c, x)} />
            : <input className="input" value={v[c] ?? ""} onChange={(e) => set(c, e.target.value)} />}
        </div>
      ))}
      <div className="sm:col-span-2 flex gap-2">
        <button disabled={save.isPending} className="btn-primary gap-2">{save.isPending && <Loader2 size={14} className="animate-spin" />} Save</button>
        <button type="button" onClick={onDone} className="btn-secondary">Cancel</button>
      </div>
    </form>
  );
}

function Table({ module, resource, cols, canWrite }: { module: string; resource: string; cols: Cols; canWrite: boolean }) {
  const [q, setQ] = useState("");
  const [form, setForm] = useState<{ row?: any } | null>(null);
  const { data, isLoading } = useOfficeRows(module, resource, q || undefined);
  const del = useOfficeDelete(module, resource);
  const immutable = module === "ledger" && resource === "journals";
  const shown = Object.entries(cols).filter(([, m]) => m.kind !== "json" && m.kind !== "text" && !m.kind.startsWith("ref:")).map(([c]) => c);
  return (
    <div>
      <div className="flex flex-wrap gap-2 mb-3 print:hidden">
        <input className="input max-w-xs" placeholder="Search" value={q} onChange={(e) => setQ(e.target.value)} />
        <button onClick={() => downloadCsv(`/office/${module}/${resource}/export`, undefined, `${module}-${resource}.csv`).catch(() => toast.error("Could not export."))} className="btn-secondary gap-1"><Download size={15} /> Export CSV</button>
        <button onClick={() => window.print()} className="btn-secondary gap-1"><Printer size={15} /> Print</button>
        {canWrite && <button onClick={() => setForm({})} className="btn-primary gap-1"><Plus size={15} /> Add {title(resource).replace(/s$/, "")}</button>}
      </div>
      {form && <Form module={module} resource={resource} cols={cols} initial={form.row} onDone={() => setForm(null)} />}
      {isLoading ? <Loader2 className="animate-spin text-slate-400 mx-auto my-8" /> : (
        <div className="bg-white border border-slate-200 rounded-xl overflow-x-auto">
          <table className="w-full text-sm min-w-[520px]">
            <thead><tr className="text-left text-xs uppercase text-slate-500 bg-slate-50">{shown.map((c) => <th key={c} className="p-2">{title(c)}</th>)}<th className="p-2 w-24" /></tr></thead>
            <tbody>
              {(data?.items ?? []).map((r) => (
                <tr key={r.id} className="border-t">
                  {shown.map((c) => <td key={c} className="p-2">{typeof r[c] === "boolean" ? (r[c] ? "Yes" : "No") : MONEY_COLS.has(c) ? money(r[c]) : String(r[c] ?? "")}</td>)}
                  <td className="p-2 text-right whitespace-nowrap">
                    {canWrite && !immutable && <button aria-label="Edit" onClick={() => setForm({ row: r })} className="p-1 text-slate-500"><Pencil size={15} /></button>}
                    {canWrite && !immutable && <button aria-label="Delete" onClick={() => confirm("Delete this record?") && del.mutate(r.id, { onError: (e: any) => toast.error(e?.response?.data?.detail ?? "Could not delete.") })} className="p-1 text-red-500"><Trash2 size={15} /></button>}
                  </td>
                </tr>
              ))}
              {!data?.items.length && <tr><td colSpan={shown.length + 1} className="p-6 text-center text-slate-400">Nothing here yet.</td></tr>}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function SyncButton() {
  const qc = useQueryClient();
  const [busy, setBusy] = useState(false);
  const run = async () => {
    setBusy(true);
    try {
      const r = (await api.post("/office/ledger/sync")).data;
      toast.success(r.journals_added ? `Added ${r.journals_added} journal(s) from fees and payroll.` : "Already up to date.");
      qc.invalidateQueries({ queryKey: ["office", "ledger"] });
    } catch { toast.error("Could not sync."); } finally { setBusy(false); }
  };
  return <button onClick={run} disabled={busy} className="btn-secondary gap-1 print:hidden"><RefreshCw size={15} className={busy ? "animate-spin" : ""} /> Sync from fees &amp; payroll</button>;
}

export default function OfficeModulePage() {
  const { module } = useParams<{ module: string }>();
  const { data: schema, isLoading, isError } = useOfficeSchema(module);
  const [tab, setTab] = useState<string>("");
  if (isLoading) return <div className="py-24 text-center"><Loader2 className="animate-spin text-slate-400 mx-auto" /></div>;
  if (isError || !schema) {
    return (
      <div className="flex flex-col items-center py-24 text-slate-400 px-8">
        <Lock size={40} className="mb-3 opacity-40" /><p className="font-semibold text-slate-700 text-lg">Not available</p>
        <p className="text-sm mt-1 text-center max-w-md">This module is switched off, or your role doesn&apos;t have access. The Super User can switch it on in Super Settings.</p>
      </div>
    );
  }
  const names = Object.keys(schema.resources);
  const active = tab || names[0];
  return (
    <div className="p-4 sm:p-8 max-w-5xl mx-auto">
      <div className="flex flex-wrap items-center gap-3 mb-4">
        <h1 className="text-2xl font-black text-slate-900 tracking-tight">{schema.label}</h1>
        {module === "ledger" && schema.can_write && <SyncButton />}
      </div>
      <Summary module={module} />
      <div className="flex gap-5 border-b border-slate-200 mb-4">
        {names.map((n) => <button key={n} onClick={() => setTab(n)} className={cn("py-2 text-sm font-semibold border-b-2 -mb-px", active === n ? "border-emerald-500 text-emerald-600" : "border-transparent text-slate-600")}>{title(n)}</button>)}
      </div>
      <Table key={active} module={module} resource={active} cols={schema.resources[active]} canWrite={schema.can_write} />
    </div>
  );
}
