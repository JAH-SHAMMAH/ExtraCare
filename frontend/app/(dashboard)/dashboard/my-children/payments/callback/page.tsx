"use client";

import { Suspense } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { remitaApi } from "@/lib/api";
import { CheckCircle2, Loader2, AlertTriangle, Clock, ArrowLeft } from "lucide-react";

const fmt = (n: number) => "₦" + n.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });

function CallbackInner() {
  const params = useSearchParams();
  const rrr = params.get("RRR") || params.get("rrr") || "";

  const { data, isLoading, isError, refetch, isRefetching } = useQuery<any>({
    queryKey: ["remita-verify", rrr],
    queryFn: () => remitaApi.verify(rrr),
    enabled: !!rrr,
  });

  return (
    <div className="p-8 max-w-lg mx-auto">
      <Link href="/dashboard/my-children/payments" className="flex items-center gap-2 text-xs text-slate-500 hover:text-slate-700 mb-5"><ArrowLeft size={14} /> Back to fees</Link>

      <div className="bg-white rounded-xl border border-slate-200 p-8 text-center">
        {!rrr ? (
          <><AlertTriangle size={40} className="mx-auto mb-3 text-amber-400" /><p className="font-bold text-slate-800">No payment reference</p><p className="text-sm text-slate-500 mt-1">We couldn’t find an RRR in this link.</p></>
        ) : isLoading ? (
          <><Loader2 size={40} className="mx-auto mb-3 text-brand-500 animate-spin" /><p className="font-bold text-slate-800">Confirming your payment…</p><p className="text-sm text-slate-500 mt-1">RRR {rrr}</p></>
        ) : isError ? (
          <><AlertTriangle size={40} className="mx-auto mb-3 text-amber-400" /><p className="font-bold text-slate-800">Couldn’t verify</p><button onClick={() => refetch()} className="mt-3 btn-secondary">Try again</button></>
        ) : data?.status === "paid" ? (
          <>
            <CheckCircle2 size={48} className="mx-auto mb-3 text-emerald-500" />
            <p className="text-lg font-black text-slate-900">Payment successful</p>
            <p className="text-2xl font-black text-emerald-600 my-2">{fmt(Number(data.amount))}</p>
            <div className="text-sm text-slate-500 space-y-1 mt-3">
              <p>RRR: <span className="font-mono text-slate-700">{data.rrr}</span></p>
              {data.paid_at && <p>Paid: {new Date(data.paid_at).toLocaleString()}</p>}
            </div>
            <p className="text-xs text-slate-400 mt-4">A receipt has been recorded against the invoice.</p>
            <Link href="/dashboard/my-children/payments" className="mt-5 inline-block btn-primary">Done</Link>
          </>
        ) : (
          <>
            <Clock size={40} className="mx-auto mb-3 text-amber-500" />
            <p className="font-bold text-slate-800">Payment pending</p>
            <p className="text-sm text-slate-500 mt-1">RRR {data?.rrr || rrr}. If you’ve paid, it can take a moment to confirm.</p>
            <button onClick={() => refetch()} disabled={isRefetching} className="mt-4 btn-secondary gap-2">{isRefetching && <Loader2 size={14} className="animate-spin" />}Check again</button>
          </>
        )}
      </div>
    </div>
  );
}

export default function RemitaCallbackPage() {
  return (
    <Suspense fallback={<div className="p-8 text-center text-slate-400"><Loader2 size={24} className="animate-spin mx-auto" /></div>}>
      <CallbackInner />
    </Suspense>
  );
}
