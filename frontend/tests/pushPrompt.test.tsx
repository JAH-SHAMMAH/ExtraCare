import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";

const post = vi.fn().mockResolvedValue({});
vi.mock("@/lib/api", () => ({ api: { put: vi.fn().mockResolvedValue({ data: {} }), get: vi.fn().mockImplementation((u: string) => Promise.resolve({ data: u === "/push/prefs" ? { kinds: { attendance: "My child arrives at or leaves school" }, values: { attendance: true } } : { key: "BAQ" } })), post: (...a: any[]) => post(...a) } }));
vi.mock("sonner", () => ({ toast: { success: vi.fn(), error: vi.fn() } }));
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { canAccessPath } from "@/lib/access";
import { PushPrompt } from "@/components/layout/PushPrompt";

function fakeBrowser(permission: string) {
  const sub = { toJSON: () => ({ endpoint: "https://push.example/1", keys: { p256dh: "a", auth: "b" } }) };
  const reg = { pushManager: { getSubscription: vi.fn().mockResolvedValue(null), subscribe: vi.fn().mockResolvedValue(sub) } };
  Object.defineProperty(navigator, "serviceWorker", { value: { register: vi.fn().mockResolvedValue(reg), ready: Promise.resolve(reg) }, configurable: true });
  (window as any).PushManager = function () {};
  (window as any).Notification = Object.assign(function () {}, { permission, requestPermission: vi.fn().mockResolvedValue("granted") });
  return reg;
}

describe("PushPrompt", () => {
  beforeEach(() => { localStorage.clear(); post.mockClear(); });

  it("asks, then sends the phone's subscription to the server when allowed", async () => {
    const reg = fakeBrowser("default");
    render(<PushPrompt />);
    fireEvent.click(await screen.findByRole("button", { name: /allow alerts/i }));
    await waitFor(() => expect(post).toHaveBeenCalledWith("/push/subscribe", expect.objectContaining({ endpoint: "https://push.example/1" })));
    expect(reg.pushManager.subscribe).toHaveBeenCalledWith(expect.objectContaining({ userVisibleOnly: true }));
  });

  it("stays out of the way when already allowed or blocked", () => {
    fakeBrowser("granted");
    render(<PushPrompt />);
    expect(screen.queryByRole("region", { name: /phone alerts/i })).toBeNull();
  });
});

import { PhoneAlertsCard } from "@/components/settings/PhoneAlertsCard";

describe("PhoneAlertsCard", () => {
  it("shows the switch off, turns alerts on, and the switch reads on", async () => {
    fakeBrowser("default");
    const reg = (await navigator.serviceWorker.ready) as any;
    (navigator.serviceWorker as any).getRegistration = vi.fn().mockResolvedValue(reg);
    render(<QueryClientProvider client={new QueryClient()}><PhoneAlertsCard /></QueryClientProvider>);
    const sw = await screen.findByRole("switch", { name: /phone alerts/i });
    expect(sw.getAttribute("aria-checked")).toBe("false");
    (window as any).Notification.permission = "granted";
    reg.pushManager.getSubscription.mockResolvedValueOnce(null).mockResolvedValue({ endpoint: "https://push.example/1" });
    fireEvent.click(sw);
    await waitFor(() => expect(screen.getByRole("switch", { name: /phone alerts/i }).getAttribute("aria-checked")).toBe("true"));
  });

  it("explains the iPhone Home Screen step instead of showing a dead switch", async () => {
    fakeBrowser("default");
    Object.defineProperty(navigator, "userAgent", { value: "Mozilla/5.0 (iPhone)", configurable: true });
    render(<QueryClientProvider client={new QueryClient()}><PhoneAlertsCard /></QueryClientProvider>);
    expect(await screen.findByText(/Add to Home Screen/i)).toBeTruthy();
    expect(screen.queryByRole("switch")).toBeNull();
  });
});


describe("Settings access", () => {
  it("opens for a parent who holds no settings permission, while Super Settings stays closed to them", () => {
    const parent = () => false;
    expect(canAccessPath("/dashboard/settings", parent)).toBe(true);
    expect(canAccessPath("/dashboard/settings/super", parent)).toBe(false);
  });
});

describe("Alerts I want", () => {
  it("shows the parent only their own choices once alerts are on, and saves a change", async () => {
    const reg = fakeBrowser("granted") as any;
    reg.pushManager.getSubscription.mockResolvedValue({ endpoint: "https://push.example/1" });
    (navigator.serviceWorker as any).getRegistration = vi.fn().mockResolvedValue(reg);
    Object.defineProperty(navigator, "userAgent", { value: "Mozilla/5.0 (Linux; Android 14)", configurable: true });
    render(<QueryClientProvider client={new QueryClient()}><PhoneAlertsCard /></QueryClientProvider>);
    const choice = await screen.findByRole("switch", { name: /my child arrives at or leaves school/i });
    expect(choice.getAttribute("aria-checked")).toBe("true");
    fireEvent.click(choice);
    const { api } = await import("@/lib/api");
    await waitFor(() => expect((api as any).put).toHaveBeenCalledWith("/push/prefs", { values: { attendance: false } }));
  });
});
