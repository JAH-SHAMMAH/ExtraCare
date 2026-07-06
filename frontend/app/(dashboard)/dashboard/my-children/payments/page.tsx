"use client";

import { useQuery, useMutation } from "@tanstack/react-query";
import { toast } from "sonner";
import { remitaApi } from "@/lib/api";
import { CreditCard, Loader2, AlertTriangle, CheckCircle2, Receipt } from "lucide-react";
import { useState } from "react";

const fmt = (n: number) => "₦" + n.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });

export default function ParentPaymentsPage() {
  const { data, isLoading, isError, refetch } = useQuery<any[]>({
    queryKey: ["remita-invoices"],
    queryFn: () => remitaApi.invoices(),
  });
  const [payingId, setPayingId] = useState<string | null>(null);

  const initiate = useMutation({
    mutationFn: (invoice_id: string) => remitaApi.initiate(invoice_id),
    onMutate: (id) => setPayingId(id),
    onSuccess: (res: any) => {
      if (res?.rrr && res?.payment_url) {
        toast.success(`RRR ${res.rrr} — redirecting to Remita…`);
        window.location.href = res.payment_url;   // Remita hosted payment, returns to /callback
      } else {
        toast.error(res?.message || "Could not start payment. Please try again.");
        setPayingId(null);
      }
    },
    onError: (e: any) => { toast.error(e?.response?.data?.detail || "Could not start payment."); setPayingId(null); },
  });

  const invoices = data ?? [];

  return (
    <div className="p-8 max-w-4xl mx-auto">
      <div className="mb-6">
        <nav className="flex items-center gap-2 text-xs text-slate-400 mb-2"><span>My Children</span><span>/</span><span className="text-brand-600 font-semibold">Pay Fees</span></nav>
        <h1 className="text-2xl font-black text-slate-900 tracking-tight">Pay Fees</h1>
        <p className="text-slate-500 text-sm mt-0.5">Outstanding invoices for your children. Pay securely with Remita.</p>
      </div>

      {isLoading ? (
        <div className="space-y-3">{Array.from({ length: 3 }).map((_, i) => <div key={i} className="h-20 bg-slate-100 rounded-xl animate-pulse" />)}</div>
      ) : isError ? (
        <div className="bg-white rounded-xl border border-slate-200 py-14 text-center"><AlertTriangle size={28} className="mx-auto mb-3 text-amber-400" /><p className="text-sm font-semibold text-slate-600">Couldn’t load your invoices.</p><button onClick={() => refetch()} className="mt-3 btn-secondary">Retry</button></div>
      ) : invoices.length === 0 ? (
        <div className="bg-white rounded-xl border border-slate-200 flex flex-col items-center justify-center py-16 text-slate-400"><CheckCircle2 size={36} className="mb-3 text-emerald-400" /><p className="font-semibold text-slate-600">No outstanding fees</p><p className="text-sm mt-1">You’re all settled up. 🎉</p></div>
      ) : (
        <div className="space-y-3">
          {invoices.map((inv) => (
            <div key={inv.id} className="bg-white rounded-xl border border-slate-200 p-5 flex flex-col md:flex-row md:items-center gap-4">
              <div className="flex-1 min-w-0">
                <p className="text-sm font-bold text-slate-900">{inv.student_name || inv.customer_name}</p>
                <p className="text-xs text-slate-500 flex items-center gap-1.5 mt-0.5"><Receipt size={12} /> Invoice {inv.number}{inv.invoice_date ? ` · ${new Date(inv.invoice_date).toLocaleDateString()}` : ""}</p>
              </div>
              <div className="text-right">
                <p className="text-lg font-black text-slate-900">{fmt(Number(inv.total))}</p>
                <p className="text-[10px] font-bold uppercase tracking-wide text-amber-600">Outstanding</p>
              </div>
              <button
                onClick={() => initiate.mutate(inv.id)}
                disabled={initiate.isPending}
                className="btn-primary gap-2 shrink-0"
              >
                {payingId === inv.id && initiate.isPending ? <Loader2 size={15} className="animate-spin" /> : <CreditCard size={15} />} Pay with Remita
              </button>
            </div>
          ))}
        </div>
      )}

      <p className="text-xs text-slate-400 mt-6">Payments are processed by Remita. After paying you’ll be returned here with a receipt.</p>
    </div>
  );
}
