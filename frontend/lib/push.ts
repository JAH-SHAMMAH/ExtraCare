import { api } from "@/lib/api";

export type PushStatus = "unsupported" | "needs-home-screen" | "blocked" | "off" | "on";

function keyToBytes(b64: string) {
  const pad = "=".repeat((4 - (b64.length % 4)) % 4);
  const raw = atob((b64 + pad).replace(/-/g, "+").replace(/_/g, "/"));
  return Uint8Array.from(raw, (c) => c.charCodeAt(0));
}

/** Whether this phone/browser can show alerts outside the app, and whether it is switched on. */
export async function pushStatus(): Promise<PushStatus> {
  const ua = navigator.userAgent;
  const ios = /iPhone|iPad|iPod/.test(ua);
  const standalone = window.matchMedia?.("(display-mode: standalone)").matches || (navigator as any).standalone;
  if (ios && !standalone) return "needs-home-screen";
  if (!("serviceWorker" in navigator) || !("PushManager" in window) || !("Notification" in window)) return "unsupported";
  if (Notification.permission === "denied") return "blocked";
  if (Notification.permission !== "granted") return "off";
  try {
    const reg = await navigator.serviceWorker.getRegistration("/sw.js");
    return (await reg?.pushManager.getSubscription()) ? "on" : "off";
  } catch { return "off"; }
}

/** Ask permission and register this device. Returns false if the person said no. */
export async function enablePush(): Promise<boolean> {
  if ((await Notification.requestPermission()) !== "granted") return false;
  const reg = await navigator.serviceWorker.register("/sw.js");
  await navigator.serviceWorker.ready;
  const { key } = (await api.get("/push/public-key")).data;
  const sub = (await reg.pushManager.getSubscription()) ?? (await reg.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: keyToBytes(key) }));
  await api.post("/push/subscribe", { ...sub.toJSON(), user_agent: navigator.userAgent });
  return true;
}

/** Stop alerts on this device. */
export async function disablePush(): Promise<void> {
  const reg = await navigator.serviceWorker.getRegistration("/sw.js");
  const sub = await reg?.pushManager.getSubscription();
  if (sub) {
    await api.post("/push/unsubscribe", { endpoint: sub.endpoint }).catch(() => undefined);
    await sub.unsubscribe();
  }
}
