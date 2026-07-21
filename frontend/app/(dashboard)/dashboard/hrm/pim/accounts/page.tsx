"use client";

import { useState } from "react";
import Link from "next/link";
import { useAccounts, useUpdateAccount, type AccountRow } from "@/hooks/useHrPim";
import { cn, getInitials } from "@/lib/utils";
import { Landmark, Search, AlertTriangle, Loader2, Check } from "lucide-react";

export default function AccountNumbersPage() {
  const [search, setSearch] = useState("");
  const { data, isLoading, isError, refetch } = useAccounts(search || undefined);
  const rows = data ?? [];

  return (
    <div className="p-8 max-w-5xl mx-auto">
      <div className="mb-6">
        <nav className="flex items-center gap-2 text-xs text-slate-400 mb-2"><span>HR Manager</span><span>/</span><span>PIM</span><span>/</span><span className="text-brand-600 font-semibold">Account Numbers</span></nav>
        <h1 className="text-2xl font-black text-slate-900 tracking-tight">Staff Account Numbers</h1>
        <p className="text-slate-500 text-sm mt-0.5">Payroll bank details for each employee.</p>
      </div>

      <div className="relative max-w-sm mb-5"><Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" /><input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search staff…" className="input pl-9" /></div>

      {isLoading ? (
        <div className="space-y-2">{Array.from({ length: 6 }).map((_, i) => <div key={i} className="h-16 bg-slate-100 rounded-lg animate-pulse" />)}</div>
      ) : isError ? (
        <div className="bg-white rounded-xl border border-slate-200 py-14 text-center"><AlertTriangle size={28} className="mx-auto mb-3 text-amber-400" /><p className="text-sm font-semibold text-slate-600">Couldn’t load accounts.</p><button onClick={() => refetch()} className="mt-3 btn-secondary">Retry</button></div>
      ) : rows.length === 0 ? (
        <div className="bg-white rounded-xl border border-slate-200 flex flex-col items-center justify-center py-16 text-slate-400"><Landmark size={34} className="mb-3 opacity-40" /><p className="font-semibold">No staff found</p></div>
      ) : (
        <div className="bg-white rounded-xl border border-slate-200 divide-y divide-slate-50">
          {rows.map((r) => <Row key={r.user_id} row={r} />)}
        </div>
      )}
    </div>
  );
}

function Row({ row }: { row: AccountRow }) {
  const update = useUpdateAccount();
  const [f, setF] = useState({
    bank_name: row.bank_name ?? "", bank_account_name: row.bank_account_name ?? "", bank_account_number: row.bank_account_number ?? "",
  });
  const dirty = (row.bank_name ?? "") !== f.bank_name || (row.bank_account_name ?? "") !== f.bank_account_name || (row.bank_account_number ?? "") !== f.bank_account_number;
  const save = () => update.mutate({ userId: row.user_id, data: { bank_name: f.bank_name || null, bank_account_name: f.bank_account_name || null, bank_account_number: f.bank_account_number || null } });

  return (
    <div className="flex flex-wrap items-center gap-3 px-4 py-3">
      <div className="flex items-center gap-2.5 min-w-[180px] flex-1">
        <div className="w-9 h-9 rounded-lg bg-slate-100 flex items-center justify-center text-slate-500 text-xs font-bold shrink-0">{getInitials(row.full_name || row.email || "?")}</div>
        <div className="min-w-0">
          <p className="text-sm font-semibold text-slate-800 truncate">{row.full_name || "—"}</p>
          <p className="text-xs text-slate-400 truncate">{row.job_title || "Staff"}{row.department ? ` · ${row.department}` : ""}</p>
        </div>
      </div>
      <input value={f.bank_name} onChange={(e) => setF({ ...f, bank_name: e.target.value })} placeholder="Bank" className="input w-32 py-1.5 text-sm" />
      <input value={f.bank_account_name} onChange={(e) => setF({ ...f, bank_account_name: e.target.value })} placeholder="Account name" className="input w-40 py-1.5 text-sm" />
      <input value={f.bank_account_number} onChange={(e) => setF({ ...f, bank_account_number: e.target.value })} placeholder="Account no." inputMode="numeric" className="input w-36 py-1.5 text-sm font-mono" />
      <button onClick={save} disabled={!dirty || update.isPending} className={cn("btn-primary gap-1 py-1.5 text-sm transition-opacity", !dirty && "opacity-0 pointer-events-none")}>
        {update.isPending ? <Loader2 size={13} className="animate-spin" /> : <Check size={13} />} Save
      </button>
    </div>
  );
}
