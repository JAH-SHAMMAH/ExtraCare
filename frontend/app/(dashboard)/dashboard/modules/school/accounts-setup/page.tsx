"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useFinanceSettings, useUpdateFinanceSettings, useAccounts } from "@/hooks/useFinance";
import { useHasPermission } from "@/components/guards/PermissionGate";
import { Settings2, Loader2, Save, Info } from "lucide-react";

type FieldKey = "default_cash_account_id" | "default_income_account_id" | "default_receivable_account_id" | "default_expense_account_id";

const FIELDS: { key: FieldKey; label: string; hint: string; type: "asset" | "income" | "expense" }[] = [
  { key: "default_cash_account_id", label: "Cash / bank", hint: "Default account money moves in/out of (petty cash, disbursements).", type: "asset" },
  { key: "default_income_account_id", label: "Fees / income", hint: "Default income account for fee revenue.", type: "income" },
  { key: "default_receivable_account_id", label: "Accounts receivable", hint: "Default asset account for what students owe.", type: "asset" },
  { key: "default_expense_account_id", label: "Expense", hint: "Default expense account for requisitions & petty cash.", type: "expense" },
];

export default function AccountsSetupPage() {
  const canWrite = useHasPermission("payments:write");
  const { data: settings, isLoading } = useFinanceSettings();
  const { data: accounts } = useAccounts({ active_only: true });
  const save = useUpdateFinanceSettings();

  const [form, setForm] = useState<Record<FieldKey, string>>({
    default_cash_account_id: "", default_income_account_id: "", default_receivable_account_id: "", default_expense_account_id: "",
  });

  useEffect(() => {
    if (settings) {
      setForm({
        default_cash_account_id: settings.default_cash_account_id ?? "",
        default_income_account_id: settings.default_income_account_id ?? "",
        default_receivable_account_id: settings.default_receivable_account_id ?? "",
        default_expense_account_id: settings.default_expense_account_id ?? "",
      });
    }
  }, [settings]);

  const byType = useMemo(() => {
    const g: Record<string, { id: string; code: string; name: string }[]> = { asset: [], income: [], expense: [] };
    (accounts ?? []).forEach((a) => { if (g[a.type]) g[a.type].push(a); });
    return g;
  }, [accounts]);

  const submit = () => {
    save.mutate({
      default_cash_account_id: form.default_cash_account_id || null,
      default_income_account_id: form.default_income_account_id || null,
      default_receivable_account_id: form.default_receivable_account_id || null,
      default_expense_account_id: form.default_expense_account_id || null,
    });
  };

  return (
    <div className="p-8 max-w-3xl mx-auto">
      <nav className="flex items-center gap-2 text-xs text-slate-400 mb-2"><span>Finance</span><span>/</span><span className="text-brand-600 font-semibold">Accounts Setup</span></nav>
      <h1 className="text-2xl font-black text-slate-900 tracking-tight">Accounts Setup</h1>
      <p className="text-slate-500 text-sm mt-0.5 mb-6">Pick the default posting accounts. Finance forms pre-fill these so you don't select them every time — you can still override on any transaction. (Account numbering itself lives in <Link href="/dashboard/modules/school/accounts" className="text-brand-600 hover:text-brand-700 font-semibold">Chart of Accounts</Link>.)</p>

      {!canWrite ? (
        <div className="bg-white rounded-xl border border-slate-200 p-10 text-center text-slate-500"><Settings2 size={32} className="mx-auto mb-3 opacity-40" /><p className="font-semibold">Read-only</p><p className="text-sm mt-1">Configuring default accounts requires <span className="font-mono">payments:write</span>.</p></div>
      ) : isLoading ? (
        <div className="space-y-3">{Array.from({ length: 4 }).map((_, i) => <div key={i} className="h-16 bg-slate-100 rounded-xl animate-pulse" />)}</div>
      ) : (
        <div className="bg-white rounded-xl border border-slate-200 p-6">
          <div className="space-y-5">
            {FIELDS.map((f) => {
              const opts = byType[f.type] ?? [];
              return (
                <div key={f.key} className="grid grid-cols-1 md:grid-cols-3 gap-3 md:items-center">
                  <div className="md:col-span-1">
                    <label className="label">{f.label}</label>
                    <p className="text-[11px] text-slate-400">{f.hint}</p>
                  </div>
                  <div className="md:col-span-2">
                    <select value={form[f.key]} onChange={(e) => setForm({ ...form, [f.key]: e.target.value })} className="input">
                      <option value="">— none —</option>
                      {opts.map((a) => <option key={a.id} value={a.id}>{a.code} {a.name}</option>)}
                    </select>
                    {opts.length === 0 && <p className="text-[11px] text-amber-600 mt-1">No {f.type} accounts yet — add one under Chart of Accounts.</p>}
                  </div>
                </div>
              );
            })}
          </div>
          <div className="flex items-start gap-2 text-xs text-slate-500 bg-slate-50 border border-slate-200 rounded-lg px-3 py-2 mt-6">
            <Info size={14} className="mt-0.5 shrink-0" />
            Each default is type-checked on save (cash/receivable = asset, fees = income, expense = expense), so a wrong account can't be set as a default.
          </div>
          <div className="flex justify-end mt-6">
            <button onClick={submit} disabled={save.isPending} className="btn-primary gap-2">{save.isPending && <Loader2 size={15} className="animate-spin" />}<Save size={15} /> Save defaults</button>
          </div>
        </div>
      )}
    </div>
  );
}
