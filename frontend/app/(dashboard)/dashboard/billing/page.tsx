"use client";

import { useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { toast } from "sonner";
import { CheckCircle2, Loader2 } from "lucide-react";
import { paymentsApi } from "@/lib/api";
import { useAuthStore } from "@/lib/store";

type TargetTier = "pro" | "enterprise";

const PLAN_PRICING: Record<TargetTier, { label: string; priceNgn: number; perks: string[] }> = {
  pro: {
    label: "Pro",
    priceNgn: 5_000,
    perks: ["Up to 50 users", "2 modules", "Advanced reports"],
  },
  enterprise: {
    label: "Enterprise",
    priceNgn: 25_000,
    perks: ["Unlimited users", "All modules", "AI assistant", "SSO"],
  },
};

export default function BillingPage() {
  const { org } = useAuthStore();
  const [pending, setPending] = useState<TargetTier | null>(null);

  const { data: cfg } = useQuery({
    queryKey: ["payments", "config"],
    queryFn: () => paymentsApi.config(),
  });

  const initMutation = useMutation({
    mutationFn: (tier: TargetTier) => paymentsApi.initialize({ target_tier: tier }),
    onMutate: (tier) => setPending(tier),
    onSuccess: (data) => {
      window.location.href = data.authorization_url;
    },
    onError: (err: any) => {
      setPending(null);
      const detail = err?.response?.data?.detail;
      toast.error(typeof detail === "string" ? detail : (detail?.message ?? "Failed to start checkout."));
    },
  });

  const currentTier = org?.subscription_tier ?? "free";

  return (
    <div className="p-8 max-w-4xl mx-auto">
      <div className="mb-8">
        <h1 className="text-2xl font-black text-slate-900 tracking-tight">Billing & Plans</h1>
        <p className="text-slate-500 text-sm mt-1">
          You are currently on the <span className="font-semibold text-slate-700">{currentTier}</span> plan.
        </p>
        {cfg && !cfg.configured && (
          <div className="mt-4 rounded-lg border border-amber-200 bg-amber-50 p-3 text-amber-800 text-sm">
            Payments provider is not configured. Set <code>PAYSTACK_SECRET_KEY</code> in the backend env to enable checkout.
          </div>
        )}
      </div>

      <div className="grid md:grid-cols-2 gap-4">
        {(Object.entries(PLAN_PRICING) as [TargetTier, typeof PLAN_PRICING[TargetTier]][]).map(([tier, info]) => {
          const isCurrent = currentTier === tier;
          const busy = pending === tier && initMutation.isPending;
          return (
            <div key={tier} className="border border-slate-200 rounded-xl p-6 bg-white shadow-sm">
              <div className="flex items-start justify-between">
                <div>
                  <h2 className="text-lg font-bold text-slate-900">{info.label}</h2>
                  <p className="text-slate-500 text-sm">
                    ₦{info.priceNgn.toLocaleString()}<span className="text-xs">/month</span>
                  </p>
                </div>
                {isCurrent && (
                  <span className="inline-flex items-center gap-1 rounded-full bg-emerald-50 text-emerald-700 px-2 py-0.5 text-xs font-semibold">
                    <CheckCircle2 className="w-3 h-3" />Current
                  </span>
                )}
              </div>
              <ul className="mt-4 space-y-1.5 text-sm text-slate-700">
                {info.perks.map((p) => <li key={p}>• {p}</li>)}
              </ul>
              <button
                type="button"
                disabled={isCurrent || busy || !cfg?.configured}
                onClick={() => initMutation.mutate(tier)}
                className="mt-5 w-full btn-primary disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {busy ? (
                  <span className="inline-flex items-center gap-2">
                    <Loader2 className="w-4 h-4 animate-spin" /> Redirecting…
                  </span>
                ) : isCurrent ? "Active plan" : `Upgrade to ${info.label}`}
              </button>
            </div>
          );
        })}
      </div>
    </div>
  );
}
