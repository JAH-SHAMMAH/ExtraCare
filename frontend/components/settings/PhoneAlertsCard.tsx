"use client";

import { useEffect, useState } from "react";
import { BellRing, Loader2 } from "lucide-react";
import { toast } from "sonner";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { disablePush, enablePush, pushStatus, type PushStatus } from "@/lib/push";

const NOTE: Record<PushStatus, string> = {
  "unsupported": "This browser cannot show alerts outside the app.",
  "needs-home-screen": "On iPhone, first tap Share, then Add to Home Screen, and open the app from your Home Screen. Then come back here.",
  "blocked": "Alerts are blocked for this app in your phone's settings. Allow notifications there, then come back here.",
  "off": "Alerts are off on this phone.",
  "on": "Alerts are on. You will see a pop-up when your child arrives at or leaves school, even when the app is closed.",
};

function Switch({ on, label, onChange, disabled }: { on: boolean; label: string; onChange: () => void; disabled?: boolean }) {
  return (
    <button role="switch" aria-checked={on} aria-label={label} onClick={onChange} disabled={disabled}
      className={`relative h-7 w-12 shrink-0 rounded-full transition-colors ${on ? "bg-emerald-500" : "bg-slate-300"}`}>
      <span className={`absolute top-0.5 h-6 w-6 rounded-full bg-white transition-all ${on ? "left-[22px]" : "left-0.5"}`} />
    </button>
  );
}

/** Which kinds of alert this person wants. Everyone sees only their own choices. */
function AlertChoices() {
  const qc = useQueryClient();
  const prefs = useQuery({ queryKey: ["push-prefs"], queryFn: () => api.get("/push/prefs").then((r) => r.data as { kinds: Record<string, string>; values: Record<string, boolean> }) });
  const save = useMutation({
    mutationFn: (v: Record<string, boolean>) => api.put("/push/prefs", { values: v }).then((r) => r.data),
    onSuccess: (d) => qc.setQueryData(["push-prefs"], d),
    onError: () => toast.error("Could not save your choice."),
  });
  if (!prefs.data) return null;
  return (
    <div className="mt-5 border-t border-slate-100 pt-4">
      <p className="text-xs font-bold uppercase tracking-wide text-slate-500 mb-2">Alerts I want</p>
      {Object.entries(prefs.data.kinds).map(([k, label]) => (
        <div key={k} className="flex items-center justify-between gap-4 py-2">
          <span className="text-sm text-slate-700">{label}</span>
          <Switch on={!!prefs.data!.values[k]} label={label} disabled={save.isPending} onChange={() => save.mutate({ [k]: !prefs.data!.values[k] })} />
        </div>
      ))}
    </div>
  );
}

/** One switch: pop-up alerts on this phone, even when the app is closed. */
export function PhoneAlertsCard() {
  const [status, setStatus] = useState<PushStatus | null>(null);
  const [busy, setBusy] = useState(false);
  useEffect(() => { pushStatus().then(setStatus); }, []);
  const usable = status === "on" || status === "off";
  const flip = async () => {
    setBusy(true);
    try {
      if (status === "on") { await disablePush(); toast.success("Phone alerts turned off."); }
      else if (await enablePush()) toast.success("Phone alerts turned on.");
      setStatus(await pushStatus());
    } catch { toast.error("Could not change phone alerts."); } finally { setBusy(false); }
  };
  return (
    <div className="bg-white rounded-xl border border-slate-200 p-6">
      <h2 className="text-sm font-bold text-slate-800 mb-3 flex items-center gap-2"><BellRing size={15} /> Phone alerts</h2>
      {status === null ? <Loader2 className="animate-spin text-slate-400" size={18} /> : (
        <div className="flex items-start justify-between gap-4">
          <p className="text-sm text-slate-600">{NOTE[status]}</p>
          {usable && (
            <Switch on={status === "on"} label="Phone alerts" onChange={flip} disabled={busy} />
          )}
        </div>
      )}
      {status === "on" && <AlertChoices />}
    </div>
  );
}
