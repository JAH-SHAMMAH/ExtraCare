import { describe, it, expect, vi } from "vitest";
import { IDLE_LIMIT_MS, isIdle, makeDebounce } from "@/lib/examRoom";

describe("exam room inactivity", () => {
  it("limit is exactly 3 minutes", () => expect(IDLE_LIMIT_MS).toBe(180_000));
  it("is idle only at or after 3 minutes without activity", () => {
    expect(isIdle(1_000 + 179_999, 1_000)).toBe(false);
    expect(isIdle(1_000 + 180_000, 1_000)).toBe(true);
  });
  it("collapses a burst of tab-switch events into one", () => {
    vi.useFakeTimers();
    const once = makeDebounce(1500);
    expect(once()).toBe(true);
    expect(once()).toBe(false);
    vi.advanceTimersByTime(2000);
    expect(once()).toBe(true);
    vi.useRealTimers();
  });
});
