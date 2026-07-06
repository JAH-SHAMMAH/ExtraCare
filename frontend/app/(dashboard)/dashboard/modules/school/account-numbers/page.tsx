"use client";

import { useState } from "react";
import { useBankAccounts, useCreateBankAccount, useUpdateBankAccount, useSetPrimaryBankAccount, useDeleteBankAccount } from "@/hooks/useFinance";
import { useHasPermission } from "@/components/guards/PermissionGate";
import { cn } from "@/lib/utils";
import { Landmark, Plus, X, Loader2, Trash2, Pencil, AlertTriangle, Star, CheckCircle2 } from "lucide-react";
import type { BankAccount } from "@/types";

const ACCOUNT_TYPES = ["current", "savings", "domiciliary"];

type FormState = { bank_name: string; account_name: string; account_number: string; bank_code: string; account_type: string; purpose: string; is_primary: boolean; notes: string };
const empty = (): FormState => ({ bank_name: "", account_name: "", account_number: "", bank_code: "", account_type: "current", purpose: "", is_primary: false, notes: "" });

export default function AccountNumbersPage() {
  const canWrite = useHasPermission("payments:write");
  const { data: accounts, isLoading, isError, refetch } = useBankAccounts();
  const create = useCreateBankAccount();
  const update = useUpdateBankAccount();
  const setPrimary = useSetPrimaryBankAccount();
  const del = useDeleteBankAccount();

  const [show, setShow] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [f, setF] = useState<FormState>(empty());

  const openCreate = () => { setEditingId(null); setF(empty()); setShow(true); };
  const openEdit = (b: BankAccount) => {
    setEditingId(b.id);
    setF({ bank_name: b.bank_name, account_name: b.account_name, account_number: b.account_number, bank_code: b.bank_code ?? "", account_type: b.account_type ?? "current", purpose: b.purpose ?? "", is_primary: b.is_primary, notes: b.notes ?? "" });
    setShow(true);
  };
  const close = () => { setShow(false); setEditingId(null); setF(empty()); };

  const canSubmit = f.bank_name.trim() && f.account_name.trim() && f.account_number.trim();
  const submit = () => {
    if (!canSubmit) return;
    const payload = {
      bank_name: f.bank_name.trim(), account_name: f.account_name.trim(), account_number: f.account_number.trim(),
      bank_code: f.bank_code.trim() || null, account_type: f.account_type || null, purpose: f.purpose.trim() || null,
      is_primary: f.is_primary, notes: f.notes.trim() || null,
    };
    if (editingId) update.mutate({ id: editingId, data: payload }, { onSuccess: close });
    else create.mutate(payload, { onSuccess: close });
  };

  const pending = create.isPending || update.isPending;

  return (
    <div className="p-8 max-w-4xl mx-auto">
      <div className="flex flex-col md:flex-row md:items-end justify-between mb-6 gap-4">
        <div>
          <nav className="flex items-center gap-2 text-xs text-slate-400 mb-2"><span>Finance</span><span>/</span><span className="text-brand-600 font-semibold">Account Numbers</span></nav>
          <h1 className="text-2xl font-black text-slate-900 tracking-tight">Account Numbers</h1>
          <p className="text-slate-500 text-sm mt-0.5">The school's bank accounts for receiving fees. The <b>primary</b> account is the default "pay to" shown on invoices and receipts.</p>
        </div>
        {canWrite && <button onClick={openCreate} className="btn-primary gap-2"><Plus size={15} /> Add Account</button>}
      </div>

      {show && canWrite && (
        <div className="bg-white rounded-xl border border-slate-200 p-6 mb-6">
          <div className="flex items-center justify-between mb-4"><h2 className="text-sm font-bold text-slate-800">{editingId ? "Edit bank account" : "Add bank account"}</h2><button onClick={close} className="text-slate-400 hover:text-slate-600"><X size={16} /></button></div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
            <div><label className="label">Bank name *</label><input value={f.bank_name} onChange={(e) => setF({ ...f, bank_name: e.target.value })} className="input" placeholder="e.g. GTBank" /></div>
            <div><label className="label">Account name *</label><input value={f.account_name} onChange={(e) => setF({ ...f, account_name: e.target.value })} className="input" placeholder="e.g. Fairview School Ltd" /></div>
            <div><label className="label">Account number *</label><input value={f.account_number} onChange={(e) => setF({ ...f, account_number: e.target.value })} className="input" placeholder="0123456789" /></div>
            <div><label className="label">Bank / sort code</label><input value={f.bank_code} onChange={(e) => setF({ ...f, bank_code: e.target.value })} className="input" placeholder="optional" /></div>
            <div><label className="label">Account type</label><select value={f.account_type} onChange={(e) => setF({ ...f, account_type: e.target.value })} className="input capitalize">{ACCOUNT_TYPES.map((t) => <option key={t} value={t}>{t}</option>)}</select></div>
            <div><label className="label">Purpose / label</label><input value={f.purpose} onChange={(e) => setF({ ...f, purpose: e.target.value })} className="input" placeholder="e.g. Fees, Salaries" /></div>
            <div className="md:col-span-2"><label className="label">Notes</label><input value={f.notes} onChange={(e) => setF({ ...f, notes: e.target.value })} className="input" placeholder="optional" /></div>
          </div>
          <label className="flex items-center gap-2 text-sm text-slate-700 mb-4"><input type="checkbox" checked={f.is_primary} onChange={(e) => setF({ ...f, is_primary: e.target.checked })} className="rounded border-slate-300" /> Make this the primary "pay to" account</label>
          <div className="flex justify-end gap-3"><button onClick={close} className="btn-secondary">Cancel</button><button onClick={submit} disabled={!canSubmit || pending} className="btn-primary gap-2">{pending && <Loader2 size={15} className="animate-spin" />}{editingId ? "Save changes" : "Add account"}</button></div>
        </div>
      )}

      {isLoading ? (
        <div className="space-y-3">{Array.from({ length: 2 }).map((_, i) => <div key={i} className="h-24 bg-slate-100 rounded-xl animate-pulse" />)}</div>
      ) : isError ? (
        <div className="bg-white rounded-xl border border-slate-200 py-14 text-center"><AlertTriangle size={28} className="mx-auto mb-3 text-amber-400" /><p className="text-sm font-semibold text-slate-600">Couldn’t load accounts.</p><button onClick={() => refetch()} className="mt-3 btn-secondary">Retry</button></div>
      ) : accounts && accounts.length > 0 ? (
        <div className="space-y-3">
          {accounts.map((b: BankAccount) => (
            <div key={b.id} className={cn("bg-white rounded-xl border p-5", b.is_primary ? "border-brand-300 ring-1 ring-brand-100" : "border-slate-200")}>
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    <p className="text-sm font-bold text-slate-900">{b.bank_name}</p>
                    {b.is_primary && <span className="badge bg-brand-50 text-brand-700 border-brand-200 gap-1"><Star size={11} /> Primary</span>}
                    {!b.is_active && <span className="badge bg-slate-100 text-slate-500 border-slate-200">Inactive</span>}
                    {b.purpose && <span className="text-[11px] text-slate-400">· {b.purpose}</span>}
                  </div>
                  <p className="text-sm text-slate-700 mt-1 font-mono">{b.account_number}</p>
                  <p className="text-xs text-slate-500">{b.account_name}{b.account_type ? ` · ${b.account_type}` : ""}{b.bank_code ? ` · ${b.bank_code}` : ""}</p>
                  {b.notes && <p className="text-[11px] text-slate-400 mt-1">{b.notes}</p>}
                </div>
                {canWrite && (
                  <div className="flex items-center gap-1 shrink-0">
                    {!b.is_primary && <button onClick={() => setPrimary.mutate(b.id)} className="inline-flex items-center gap-1 text-xs font-semibold text-brand-600 hover:text-brand-700 px-2 py-1 rounded hover:bg-brand-50"><CheckCircle2 size={13} /> Set primary</button>}
                    <button onClick={() => openEdit(b)} className="text-slate-400 hover:text-brand-600 p-1" title="Edit"><Pencil size={14} /></button>
                    <button onClick={() => { if (confirm("Remove this bank account?")) del.mutate(b.id); }} className="text-slate-400 hover:text-red-600 p-1" title="Remove"><Trash2 size={14} /></button>
                  </div>
                )}
              </div>
            </div>
          ))}
        </div>
      ) : (
        <div className="bg-white rounded-xl border border-slate-200 py-16 text-center text-slate-400"><Landmark size={36} className="mx-auto mb-3 opacity-40" /><p className="font-semibold">No bank accounts yet</p>{canWrite && <button onClick={openCreate} className="text-brand-600 hover:text-brand-700 text-sm font-semibold mt-1">Add your first account →</button>}</div>
      )}
    </div>
  );
}
