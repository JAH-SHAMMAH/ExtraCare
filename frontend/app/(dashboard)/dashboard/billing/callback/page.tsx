"use client";

import { useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, XCircle, Loader2, ArrowRight } from "lucide-react";
import { paymentsApi } from "@/lib/api";

type VerifyState =
  | { status: "loading" }
  | { status: "success"; tier: string; tierUpgraded: boolean; amount: number }
  | { status: "failed"; message: string };

export default function BillingCallbackPage() {
  const router = useRouter();
  const params = useSearchParams();
  const reference = params.get("reference") ?? params.get("trxref");
  const queryClient = useQueryClient();

  const [state, setState] = useState<VerifyState>({ status: "loading" });

  useEffect(() => {
    if (!reference) {
      setState({ status: "failed", message: "Missing payment reference in callback URL." });
      return;
    }
    let cancelled = false;
    (async () => {
      try {
        const data = await paymentsApi.verify(reference);
        if (cancelled) return;
        if (data.status === "success") {
          setState({
            status: "success",
            tier: data.target_tier,
            tierUpgraded: !!data.tier_upgraded,
            amount: data.amount,
          });
          // Refetch /auth/me so the auth store picks up the new tier + features.
          await queryClient.invalidateQueries({ queryKey: ["me"] });
        } else {
          setState({ status: "failed", message: data.message ?? "Payment was not successful." });
        }
      } catch (err: any) {
        if (cancelled) return;
        const detail = err?.response?.data?.detail;
        const msg = typeof detail === "string" ? detail : (detail?.message ?? "Could not verify payment.");
        setState({ status: "failed", message: msg });
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [reference, queryClient]);

  return (
    <div className="p-8 max-w-xl mx-auto">
      <div className="rounded-xl border border-slate-200 bg-white shadow-sm p-8">
        {state.status === "loading" && (
          <div className="flex flex-col items-center text-center gap-3 py-6">
            <Loader2 className="w-10 h-10 text-slate-400 animate-spin" />
            <h1 className="text-lg font-bold text-slate-900">Verifying your payment…</h1>
            <p className="text-sm text-slate-500">This usually takes a few seconds.</p>
          </div>
        )}

        {state.status === "success" && (
          <div className="flex flex-col items-center text-center gap-3 py-2">
            <CheckCircle2 className="w-12 h-12 text-emerald-500" />
            <h1 className="text-xl font-black text-slate-900 tracking-tight">Payment confirmed</h1>
            <p className="text-sm text-slate-600">
              ₦{state.amount.toLocaleString()} received.{" "}
              {state.tierUpgraded ? (
                <>You are now on the <span className="font-semibold">{state.tier}</span> plan.</>
              ) : (
                <>Your <span className="font-semibold">{state.tier}</span> plan is already active.</>
              )}
            </p>
            <button
              type="button"
              onClick={() => router.push("/dashboard/billing")}
              className="mt-4 btn-primary inline-flex items-center gap-2"
            >
              Back to billing <ArrowRight className="w-4 h-4" />
            </button>
          </div>
        )}

        {state.status === "failed" && (
          <div className="flex flex-col items-center text-center gap-3 py-2">
            <XCircle className="w-12 h-12 text-red-500" />
            <h1 className="text-xl font-black text-slate-900 tracking-tight">Payment not verified</h1>
            <p className="text-sm text-slate-600">{state.message}</p>
            <button
              type="button"
              onClick={() => router.push("/dashboard/billing")}
              className="mt-4 btn-primary"
            >
              Try again
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
