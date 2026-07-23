"use client";

import { useMemo, useState } from "react";
import { useWallets, usePocketMoneyItems, useCreatePMTransaction } from "@/hooks/useWallet";
import { useAccounts } from "@/hooks/useFinance";
import { useHasPermission } from "@/components/guards/PermissionGate";
import { formatCurrency } from "@/lib/utils";
import { Receipt, Plus, Trash2, Loader2, Lock } from "lucide-react";

type Line = { item_id: string; qty: number };

export default function NewPocketMoneyTransactionPage() {
  const canSpend = useHasPermission("wallet:spend");
  const { data: walletsData } = useWallets();
  const { data: items } = usePocketMoneyItems(true);
  const { data: accounts } = useAccounts({ active_only: true });
  const create = useCreatePMTransaction();

  const wallets = walletsData?.items ?? [];
  const incomeAccts = useMemo(() => (accounts ?? []).filter((a) => a.type === "income"), [accounts]);
  const itemList = items ?? [];
  const priceOf = (id: string) => itemList.find((i) => i.id === id)?.unit_price ?? 0;

  const [walletId, setWalletId] = useState("");
  const [incomeId, setIncomeId] = useState("");
  const [memo, setMemo] = useState("");
  const [lines, setLines] = useState<Line[]>([]);
  const [directAmount, setDirectAmount] = useState("");

  const total = lines.reduce((s, l) => s + priceOf(l.item_id) * l.qty, 0);
  const effectiveAmount = lines.length > 0 ? total : Number(directAmount || 0);
  const selectedWallet = wallets.find((w) => w.id === walletId);

  const submit = () => {
    const data: any = { wallet_id: walletId, income_account_id: incomeId, memo: memo || null };
    if (lines.length > 0) data.lines = lines.filter((l) => l.item_id).map((l) => ({ item_id: l.item_id, qty: l.qty }));
    else data.amount = Number(directAmount);
    create.mutate(data, { onSuccess: () => { setLines([]); setDirectAmount(""); setMemo(""); } });
  };

  const canSubmit = canSpend && walletId && incomeId && effectiveAmount > 0 && (lines.length === 0 || lines.every((l) => l.item_id));

  if (!canSpend) return (
    <div className="p-8 max-w-2xl mx-auto"><div className="bg-white rounded-xl border border-slate-200 py-16 text-center text-slate-400"><Lock size={30} className="mx-auto mb-3 opacity-50" /><p className="font-semibold text-slate-600">Recording a transaction requires the wallet:spend permission.</p></div></div>
  );

  return (
    <div className="p-8 max-w-2xl mx-auto">
      <div className="mb-6">
        <nav className="flex items-center gap-2 text-xs text-slate-400 mb-2"><span>PocketMoney Manager</span><span>/</span><span className="text-brand-600 font-semibold">New Transaction</span></nav>
        <h1 className="text-2xl font-black text-slate-900 tracking-tight">New Transaction</h1>
        <p className="text-slate-500 text-sm mt-0.5">Record a purchase against a student’s pocket-money wallet. No overdraw; the daily limit is enforced.</p>
      </div>

      <div className="bg-white rounded-xl border border-slate-200 p-6 space-y-5">
        <div>
          <label className="label">Student wallet *</label>
          <select value={walletId} onChange={(e) => setWalletId(e.target.value)} className="input">
            <option value="">Select a wallet…</option>
            {wallets.map((w) => <option key={w.id} value={w.id} disabled={!w.is_active}>{w.student_name || w.student_id.slice(0, 8)} — balance {w.balance.toFixed(2)}{w.is_active ? "" : " (inactive)"}</option>)}
          </select>
          {selectedWallet && <p className="text-xs text-slate-400 mt-1">Balance {formatCurrency(selectedWallet.balance)}{selectedWallet.spend_limit_daily != null ? ` · daily limit ${formatCurrency(selectedWallet.spend_limit_daily)}` : ""}</p>}
        </div>

        {/* Itemised lines */}
        <div>
          <div className="flex items-center justify-between mb-2"><label className="label mb-0">Items</label><button onClick={() => setLines([...lines, { item_id: "", qty: 1 }])} className="inline-flex items-center gap-1 text-xs font-semibold text-brand-600 hover:text-brand-700"><Plus size={13} /> Add item</button></div>
          {lines.length === 0 ? (
            <p className="text-xs text-slate-400">No items — or enter a direct amount below.</p>
          ) : (
            <div className="space-y-2">
              {lines.map((l, idx) => (
                <div key={idx} className="flex items-center gap-2">
                  <select value={l.item_id} onChange={(e) => setLines(lines.map((x, i) => i === idx ? { ...x, item_id: e.target.value } : x))} className="input flex-1">
                    <option value="">Select item…</option>
                    {itemList.map((it) => <option key={it.id} value={it.id}>{it.name} — {it.unit_price.toFixed(2)}</option>)}
                  </select>
                  <input type="number" min={1} value={l.qty} onChange={(e) => setLines(lines.map((x, i) => i === idx ? { ...x, qty: Math.max(1, Number(e.target.value)) } : x))} className="input w-20" />
                  <span className="text-sm font-semibold text-slate-600 w-24 text-right">{formatCurrency(priceOf(l.item_id) * l.qty)}</span>
                  <button onClick={() => setLines(lines.filter((_, i) => i !== idx))} className="text-rose-400 hover:text-rose-600 p-1"><Trash2 size={15} /></button>
                </div>
              ))}
              <div className="flex justify-end pt-1 text-sm font-bold text-slate-800">Total: {formatCurrency(total)}</div>
            </div>
          )}
        </div>

        {lines.length === 0 && (
          <div><label className="label">Or amount directly *</label><input type="number" value={directAmount} onChange={(e) => setDirectAmount(e.target.value)} className="input" placeholder="0.00" /></div>
        )}

        <div><label className="label">Sold as (income account) *</label><select value={incomeId} onChange={(e) => setIncomeId(e.target.value)} className="input"><option value="">Select…</option>{incomeAccts.map((a) => <option key={a.id} value={a.id}>{a.code} {a.name}</option>)}</select></div>
        <div><label className="label">Memo</label><input value={memo} onChange={(e) => setMemo(e.target.value)} className="input" placeholder="optional — defaults to the item list" /></div>

        <div className="flex items-center justify-between border-t border-slate-100 pt-4">
          <span className="text-sm text-slate-500">Charge: <span className="font-bold text-slate-900">{formatCurrency(effectiveAmount)}</span></span>
          <button onClick={submit} disabled={!canSubmit || create.isPending} className="btn-primary gap-2">{create.isPending ? <Loader2 size={15} className="animate-spin" /> : <Receipt size={15} />} Record transaction</button>
        </div>
      </div>
    </div>
  );
}
