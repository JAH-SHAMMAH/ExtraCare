"use client";

import { useQuery, useMutation } from "@tanstack/react-query";
import { toast } from "sonner";
import { remitaApi, feesApi } from "@/lib/api";
import { cn } from "@/lib/utils";
import { CreditCard, Loader2, AlertTriangle, CheckCircle2, Receipt } from "lucide-react";
import { useState } from "react";

const fmt = (n: number) => "₦" + n.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const PROVIDER_LABEL: Record<string, string> = { remita: "Remita", paystack: "Paystack", flutterwave: "Flutterwave" };

export default function ParentPaymentsPage() {
  const { data: invData, isLoading, isError, refetch } = useQuery<any[]>({
    queryKey: ["fee-invoices"],
    queryFn: () => remitaApi.invoices(),   // invoice list is provider-agnostic
  });
  // Which gateway(s) has the school actually configured?
  const { data: provData } = useQuery<{ providers: string[] }>({
    queryKey: ["fee-providers"],
    queryFn: () => feesApi.providers(),
  });
  const providers = provData?.providers ?? [];
  const [chosen, setChosen] = useState<string | null>(null);
  const provider = chosen ?? providers[0] ?? null;   // default to the first available

  const [payingId, setPayingId] = useState<string | null>(null);

  const initiate = useMutation({
    mutationFn: ({ invoice_id, provider }: { invoice_id: string; provider: string }) =>
      provider === "remita" ? remitaApi.initiate(invoice_id) : feesApi.initiate(invoice_id, provider),
    onMutate: ({ invoice_id }) => setPayingId(invoice_id),
    onSuccess: (res: any) => {
      const url = res?.payment_url || res?.authorization_url;   // Remita vs card
      if (url) {
        toast.success("Redirecting to secure checkout…");
        window.location.href = url;   // hosted payment; returns to /callback
      } else {
        toast.error(res?.message || "Could not start payment. Please try again.");
        setPayingId(null);
      }
    },
    onError: (e: any) => { toast.error(e?.response?.data?.detail || "Could not start payment."); setPayingId(null); },
  });

  const invoices = invData ?? [];

  return (
    <div className="p-8 max-w-4xl mx-auto">
      <div className="mb-6">
        <nav className="flex items-center gap-2 text-xs text-slate-400 mb-2"><span>My Children</span><span>/</span><span className="text-brand-600 font-semibold">Pay Fees</span></nav>
        <h1 className="text-2xl font-black text-slate-900 tracking-tight">Pay Fees</h1>
        <p className="text-slate-500 text-sm mt-0.5">Outstanding invoices for your children. Pay securely online.</p>
      </div>

      {/* Provider selector — only shown when the school configured more than one. */}
      {providers.length > 1 && (
        <div className="bg-white rounded-xl border border-slate-200 p-4 mb-4">
          <p className="text-[11px] font-bold uppercase tracking-widest text-slate-500 mb-2">Pay with</p>
          <div className="flex flex-wrap gap-2">
            {providers.map((p) => (
              <button key={p} onClick={() => setChosen(p)}
                className={cn("px-4 py-2 rounded-lg text-sm font-semibold border transition",
                  provider === p ? "bg-brand-600 text-white border-brand-600" : "bg-white text-slate-600 border-slate-200 hover:border-slate-300")}>
                {PROVIDER_LABEL[p] ?? p}
              </button>
            ))}
          </div>
        </div>
      )}

      {isLoading ? (
        <div className="space-y-3">{Array.from({ length: 3 }).map((_, i) => <div key={i} className="h-20 bg-slate-100 rounded-xl animate-pulse" />)}</div>
      ) : isError ? (
        <div className="bg-white rounded-xl border border-slate-200 py-14 text-center"><AlertTriangle size={28} className="mx-auto mb-3 text-amber-400" /><p className="text-sm font-semibold text-slate-600">Couldn’t load your invoices.</p><button onClick={() => refetch()} className="mt-3 btn-secondary">Retry</button></div>
      ) : invoices.length === 0 ? (
        <div className="bg-white rounded-xl border border-slate-200 flex flex-col items-center justify-center py-16 text-slate-400"><CheckCircle2 size={36} className="mb-3 text-emerald-400" /><p className="font-semibold text-slate-600">No outstanding fees</p><p className="text-sm mt-1">You’re all settled up. 🎉</p></div>
      ) : provider === null ? (
        <div className="bg-white rounded-xl border border-slate-200 py-14 text-center"><AlertTriangle size={28} className="mx-auto mb-3 text-amber-400" /><p className="text-sm font-semibold text-slate-600">Online payment isn’t set up yet.</p><p className="text-xs text-slate-400 mt-1">Please contact the school to pay your fees.</p></div>
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
                onClick={() => initiate.mutate({ invoice_id: inv.id, provider })}
                disabled={initiate.isPending}
                className="btn-primary gap-2 shrink-0"
              >
                {payingId === inv.id && initiate.isPending ? <Loader2 size={15} className="animate-spin" /> : <CreditCard size={15} />} Pay with {PROVIDER_LABEL[provider] ?? provider}
              </button>
            </div>
          ))}
        </div>
      )}

      <p className="text-xs text-slate-400 mt-6">Payments are processed securely by your school’s payment provider. After paying you’ll be returned here with a receipt.</p>
    </div>
  );
}
