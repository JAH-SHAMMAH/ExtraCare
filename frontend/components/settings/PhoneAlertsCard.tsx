"use client";

import { useEffect, useState } from "react";
import { BellRing, Loader2 } from "lucide-react";
import { toast } from "sonner";
import { disablePush, enablePush, pushStatus, type PushStatus } from "@/lib/push";

const NOTE: Record<PushStatus, string> = {
  "unsupported": "This browser cannot show alerts outside the app.",
  "needs-home-screen": "On iPhone, first tap Share, then Add to Home Screen, and open the app from your Home Screen. Then come back here.",
  "blocked": "Alerts are blocked for this app in your phone's settings. Allow notifications there, then come back here.",
  "off": "Alerts are off on this phone.",
  "on": "Alerts are on. You will see a pop-up when your child arrives at or leaves school, even when the app is closed.",
};

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
            <button role="switch" aria-checked={status === "on"} aria-label="Phone alerts" onClick={flip} disabled={busy}
              className={`relative h-7 w-12 shrink-0 rounded-full transition-colors ${status === "on" ? "bg-emerald-500" : "bg-slate-300"}`}>
              <span className={`absolute top-0.5 h-6 w-6 rounded-full bg-white transition-all ${status === "on" ? "left-[22px]" : "left-0.5"}`} />
            </button>
          )}
        </div>
      )}
    </div>
  );
}
