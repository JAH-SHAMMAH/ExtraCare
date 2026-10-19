import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";

const post = vi.fn().mockResolvedValue({});
vi.mock("@/lib/api", () => ({ api: { get: vi.fn().mockResolvedValue({ data: { key: "BAQ" } }), post: (...a: any[]) => post(...a) } }));
vi.mock("sonner", () => ({ toast: { success: vi.fn(), error: vi.fn() } }));
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
