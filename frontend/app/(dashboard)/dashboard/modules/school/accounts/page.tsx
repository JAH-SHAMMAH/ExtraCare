"use client";

import { useState } from "react";
import {
  useAccounts, useCreateAccount, useUpdateAccount, useDeleteAccount,
  usePeriods, useCreatePeriod, useLockPeriod,
} from "@/hooks/useFinance";
import { useHasPermission } from "@/components/guards/PermissionGate";
import { cn } from "@/lib/utils";
import { BookOpen, Plus, X, Loader2, Trash2, AlertTriangle, Lock, Unlock, CalendarRange } from "lucide-react";
import type { LedgerAccount } from "@/types";

const TYPES = ["asset", "liability", "equity", "income", "expense"];

export default function ChartOfAccountsPage() {
  const canWrite = useHasPermission("payments:write");
  const canPost = useHasPermission("payments:post");
  const [tab, setTab] = useState<"accounts" | "periods">("accounts");

  return (
    <div className="p-8 max-w-6xl mx-auto">
      <div className="mb-6">
        <nav className="flex items-center gap-2 text-xs text-slate-400 mb-2"><span>Finance</span><span>/</span><span className="text-brand-600 font-semibold">Chart of Accounts</span></nav>
        <h1 className="text-2xl font-black text-slate-900 tracking-tight">Chart of Accounts</h1>
        <p className="text-slate-500 text-sm mt-0.5">The accounts every ledger posting references, and the financial periods you can lock.</p>
      </div>

      <div className="flex gap-1 border-b border-slate-200 mb-6">
        {([["accounts", "Accounts"], ["periods", "Periods"]] as const).map(([key, label]) => (
          <button key={key} onClick={() => setTab(key)} className={cn("px-4 py-2 text-sm font-semibold border-b-2 -mb-px transition", tab === key ? "border-brand-600 text-brand-700" : "border-transparent text-slate-500 hover:text-slate-700")}>{label}</button>
        ))}
      </div>

      {tab === "accounts" ? <AccountsTab canWrite={canWrite} /> : <PeriodsTab canWrite={canWrite} canPost={canPost} />}
    </div>
  );
}

function AccountsTab({ canWrite }: { canWrite: boolean }) {
  const { data: accounts, isLoading, isError, refetch } = useAccounts();
  const create = useCreateAccount();
  const update = useUpdateAccount();
  const remove = useDeleteAccount();
  const [show, setShow] = useState(false);
  const [form, setForm] = useState({ code: "", name: "", type: "asset", description: "" });

  const reset = () => { setForm({ code: "", name: "", type: "asset", description: "" }); setShow(false); };
  const submit = () => create.mutate({ code: form.code.trim(), name: form.name.trim(), type: form.type, description: form.description || null }, { onSuccess: reset });

  return (
    <>
      <div className="flex justify-end mb-4">
        {canWrite && <button onClick={() => { reset(); setShow(true); }} className="btn-primary gap-2"><Plus size={15} /> New Account</button>}
      </div>
      {show && canWrite && (
        <div className="bg-white rounded-xl border border-slate-200 p-6 mb-6">
          <div className="flex items-center justify-between mb-4"><h2 className="text-sm font-bold text-slate-800">New Account</h2><button onClick={reset} className="text-slate-400 hover:text-slate-600"><X size={16} /></button></div>
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            <div><label className="label">Code *</label><input value={form.code} onChange={(e) => setForm({ ...form, code: e.target.value })} className="input" placeholder="1000" /></div>
            <div className="md:col-span-2"><label className="label">Name *</label><input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} className="input" placeholder="Cash at Bank" /></div>
            <div><label className="label">Type *</label><select value={form.type} onChange={(e) => setForm({ ...form, type: e.target.value })} className="input capitalize">{TYPES.map((t) => <option key={t} value={t}>{t}</option>)}</select></div>
            <div className="md:col-span-4"><label className="label">Description</label><input value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} className="input" /></div>
          </div>
          <div className="flex justify-end gap-3 mt-4"><button onClick={reset} className="btn-secondary">Cancel</button><button onClick={submit} disabled={!form.code.trim() || !form.name.trim() || create.isPending} className="btn-primary gap-2">{create.isPending && <Loader2 size={15} className="animate-spin" />}Create</button></div>
        </div>
      )}

      {isLoading ? (
        <div className="space-y-2">{Array.from({ length: 6 }).map((_, i) => <div key={i} className="h-10 bg-slate-100 rounded-lg animate-pulse" />)}</div>
      ) : isError ? (
        <div className="bg-white rounded-xl border border-slate-200 py-14 text-center"><AlertTriangle size={28} className="mx-auto mb-3 text-amber-400" /><p className="text-sm font-semibold text-slate-600">Couldn’t load accounts.</p><button onClick={() => refetch()} className="mt-3 btn-secondary">Retry</button></div>
      ) : accounts && accounts.length > 0 ? (
        <div className="space-y-6">
          {TYPES.map((t) => {
            const group = accounts.filter((a) => a.type === t);
            if (group.length === 0) return null;
            return (
              <div key={t}>
                <h3 className="text-[11px] font-bold uppercase tracking-widest text-slate-400 mb-2">{t}</h3>
                <div className="bg-white rounded-xl border border-slate-200 divide-y divide-slate-50">
                  {group.map((a) => (
                    <div key={a.id} className="flex items-center gap-3 px-5 py-3">
                      <span className="text-xs font-mono text-slate-400 w-16">{a.code}</span>
                      <span className={cn("text-sm flex-1", a.is_active ? "text-slate-800" : "text-slate-400 line-through")}>{a.name}</span>
                      {canWrite && (
                        <>
                          <button onClick={() => update.mutate({ id: a.id, data: { is_active: !a.is_active } })} className="text-xs font-semibold text-slate-400 hover:text-slate-600">{a.is_active ? "Deactivate" : "Activate"}</button>
                          <button onClick={() => { if (confirm("Delete this account? (only if unused)")) remove.mutate(a.id); }} className="text-slate-400 hover:text-red-600 p-1"><Trash2 size={14} /></button>
                        </>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            );
          })}
        </div>
      ) : (
        <div className="bg-white rounded-xl border border-slate-200 flex flex-col items-center justify-center py-16 text-slate-400"><BookOpen size={36} className="mb-3 opacity-40" /><p className="font-semibold">No accounts yet</p></div>
      )}
    </>
  );
}

function PeriodsTab({ canWrite, canPost }: { canWrite: boolean; canPost: boolean }) {
  const { data: periods, isLoading, isError, refetch } = usePeriods();
  const create = useCreatePeriod();
  const lock = useLockPeriod();
  const [show, setShow] = useState(false);
  const [form, setForm] = useState({ name: "", start_date: "", end_date: "" });

  const reset = () => { setForm({ name: "", start_date: "", end_date: "" }); setShow(false); };
  const submit = () => create.mutate({ name: form.name.trim(), start_date: form.start_date, end_date: form.end_date }, { onSuccess: reset });

  return (
    <>
      <div className="flex justify-between items-center mb-4">
        <p className="text-xs text-slate-500">Locking a period blocks any (back-dated) posting into it.</p>
        {canWrite && <button onClick={() => { reset(); setShow(true); }} className="btn-primary gap-2"><Plus size={15} /> New Period</button>}
      </div>
      {show && canWrite && (
        <div className="bg-white rounded-xl border border-slate-200 p-6 mb-6 grid grid-cols-1 md:grid-cols-4 gap-4 items-end">
          <div className="md:col-span-2"><label className="label">Name *</label><input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} className="input" placeholder="2025/2026 Term 1" /></div>
          <div><label className="label">Start *</label><input type="date" value={form.start_date} onChange={(e) => setForm({ ...form, start_date: e.target.value })} className="input" /></div>
          <div><label className="label">End *</label><input type="date" value={form.end_date} onChange={(e) => setForm({ ...form, end_date: e.target.value })} className="input" /></div>
          <div className="md:col-span-4 flex justify-end gap-3"><button onClick={reset} className="btn-secondary">Cancel</button><button onClick={submit} disabled={!form.name.trim() || !form.start_date || !form.end_date || create.isPending} className="btn-primary gap-2">{create.isPending && <Loader2 size={15} className="animate-spin" />}Create</button></div>
        </div>
      )}

      <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
        <table className="w-full text-left">
          <thead><tr className="bg-slate-50/80 border-b border-slate-100">{["Period", "Start", "End", "Status", ""].map((h) => <th key={h} className="px-5 py-3.5 text-[10px] font-bold uppercase tracking-widest text-slate-500">{h}</th>)}</tr></thead>
          <tbody className="divide-y divide-slate-50">
            {isLoading ? (
              Array.from({ length: 3 }).map((_, i) => <tr key={i}>{Array.from({ length: 5 }).map((_, j) => <td key={j} className="px-5 py-4"><div className="h-4 bg-slate-100 rounded animate-pulse w-20" /></td>)}</tr>)
            ) : isError ? (
              <tr><td colSpan={5} className="py-14 text-center"><AlertTriangle size={28} className="mx-auto mb-3 text-amber-400" /><p className="text-sm font-semibold text-slate-600">Couldn’t load periods.</p><button onClick={() => refetch()} className="mt-3 btn-secondary">Retry</button></td></tr>
            ) : periods && periods.length > 0 ? (
              periods.map((p) => (
                <tr key={p.id} className="hover:bg-slate-50/70">
                  <td className="px-5 py-4 text-sm font-medium text-slate-800">{p.name}</td>
                  <td className="px-5 py-4 text-xs text-slate-500">{p.start_date}</td>
                  <td className="px-5 py-4 text-xs text-slate-500">{p.end_date}</td>
                  <td className="px-5 py-4"><span className={cn("badge capitalize inline-flex items-center gap-1", p.status === "locked" ? "bg-rose-50 text-rose-700 border-rose-200" : "bg-emerald-50 text-emerald-700 border-emerald-200")}>{p.status === "locked" ? <Lock size={11} /> : <Unlock size={11} />}{p.status}</span></td>
                  <td className="px-5 py-4">
                    {canPost && (
                      <button onClick={() => lock.mutate({ id: p.id, lock: p.status !== "locked" })} className="text-xs font-semibold text-brand-600 hover:text-brand-700">
                        {p.status === "locked" ? "Unlock" : "Lock"}
                      </button>
                    )}
                  </td>
                </tr>
              ))
            ) : (
              <tr><td colSpan={5} className="py-16 text-center text-slate-400"><CalendarRange size={36} className="mx-auto mb-3 opacity-40" /><p className="font-semibold">No periods yet</p></td></tr>
            )}
          </tbody>
        </table>
      </div>
    </>
  );
}
