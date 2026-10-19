"use client";

import { useEffect, useState } from "react";
import { BellRing, X } from "lucide-react";
import { toast } from "sonner";
import { api } from "@/lib/api";

const KEY = "push-prompt-dismissed";

function keyToBytes(b64: string) {
  const pad = "=".repeat((4 - (b64.length % 4)) % 4);
  const raw = atob((b64 + pad).replace(/-/g, "+").replace(/_/g, "/"));
  return Uint8Array.from(raw, (c) => c.charCodeAt(0));
}

/** Asks once whether this phone may show school alerts (a child arriving or leaving, etc.) outside the app. */
export function PushPrompt() {
  const [state, setState] = useState<"hidden" | "ask" | "ios" | "busy">("hidden");

  useEffect(() => {
    try {
      if (localStorage.getItem(KEY)) return;
    } catch { /* storage blocked: still show the prompt */ }
    const ua = navigator.userAgent;
    const ios = /iPhone|iPad|iPod/.test(ua);
    const standalone = (window.matchMedia?.("(display-mode: standalone)").matches) || (navigator as any).standalone;
    const supported = "serviceWorker" in navigator && "PushManager" in window && "Notification" in window;
    if (ios && !standalone) { setState("ios"); return; }
    if (!supported || Notification.permission !== "default") return;
    setState("ask");
  }, []);

  const dismiss = () => { try { localStorage.setItem(KEY, "1"); } catch { /* ignore */ } setState("hidden"); };

  const allow = async () => {
    setState("busy");
    try {
      const perm = await Notification.requestPermission();
      if (perm !== "granted") { dismiss(); return; }
      const reg = await navigator.serviceWorker.register("/sw.js");
      await navigator.serviceWorker.ready;
      const { key } = (await api.get("/push/public-key")).data;
      const sub = (await reg.pushManager.getSubscription()) ?? (await reg.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: keyToBytes(key) }));
      await api.post("/push/subscribe", { ...sub.toJSON(), user_agent: navigator.userAgent });
      toast.success("Done. You will get school alerts on this phone.");
      dismiss();
    } catch {
      toast.error("Could not turn on phone alerts.");
      setState("ask");
    }
  };

  if (state === "hidden") return null;
  return (
    <div role="region" aria-label="Phone alerts" className="mx-4 mt-3 sm:mx-8 flex items-start gap-3 rounded-xl border border-emerald-200 bg-emerald-50 p-3 text-sm text-emerald-900 print:hidden">
      <BellRing size={20} className="mt-0.5 shrink-0" />
      <div className="flex-1">
        {state === "ios" ? (
          <p>To get alerts on this iPhone, tap <b>Share</b>, choose <b>Add to Home Screen</b>, then open the app from your Home Screen and tap Allow.</p>
        ) : (
          <>
            <p className="font-semibold">Get alerts on your phone</p>
            <p>See a pop-up when your child arrives at or leaves school, even when this app is closed.</p>
            <button onClick={allow} disabled={state === "busy"} className="btn-primary mt-2">Allow alerts</button>
          </>
        )}
      </div>
      <button onClick={dismiss} aria-label="Dismiss" className="p-1 text-emerald-700"><X size={16} /></button>
    </div>
  );
}
