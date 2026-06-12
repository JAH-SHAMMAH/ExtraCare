import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { createReconnectController } from "@/lib/live/reconnect";

describe("reconnect.createReconnectController", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });
  afterEach(() => {
    vi.useRealTimers();
  });

  it("schedules a reconnect and invokes the connect fn", () => {
    const connect = vi.fn();
    const ctrl = createReconnectController(connect, { baseDelayMs: 500, jitterPct: 0 });
    ctrl.schedule();
    expect(connect).not.toHaveBeenCalled();
    vi.advanceTimersByTime(500);
    expect(connect).toHaveBeenCalledTimes(1);
    expect(ctrl.attempts()).toBe(1);
  });

  it("gives up after maxAttempts", () => {
    const connect = vi.fn();
    const onGiveUp = vi.fn();
    const ctrl = createReconnectController(connect, {
      maxAttempts: 2,
      baseDelayMs: 100,
      jitterPct: 0,
      onGiveUp,
    });
    ctrl.schedule();
    vi.advanceTimersByTime(100);
    ctrl.schedule();
    vi.advanceTimersByTime(200);
    // Third schedule should trigger give-up, not a timer.
    ctrl.schedule();
    expect(onGiveUp).toHaveBeenCalledTimes(1);
    expect(connect).toHaveBeenCalledTimes(2);
  });

  it("reset() clears attempts and cancels pending timer", () => {
    const connect = vi.fn();
    const ctrl = createReconnectController(connect, { baseDelayMs: 500, jitterPct: 0 });
    ctrl.schedule();
    ctrl.reset();
    vi.advanceTimersByTime(1000);
    expect(connect).not.toHaveBeenCalled();
    expect(ctrl.attempts()).toBe(0);
  });

  it("cancel() blocks further schedules", () => {
    const connect = vi.fn();
    const onGiveUp = vi.fn();
    const ctrl = createReconnectController(connect, {
      maxAttempts: 5,
      baseDelayMs: 100,
      jitterPct: 0,
      onGiveUp,
    });
    ctrl.cancel();
    ctrl.schedule();
    expect(onGiveUp).toHaveBeenCalled();
    vi.advanceTimersByTime(5000);
    expect(connect).not.toHaveBeenCalled();
  });

  it("uses exponential backoff with a cap", () => {
    const connect = vi.fn();
    const onAttempt = vi.fn();
    const ctrl = createReconnectController(connect, {
      baseDelayMs: 100,
      maxDelayMs: 1_000,
      jitterPct: 0,
      onAttempt,
    });
    for (let i = 0; i < 5; i++) {
      ctrl.schedule();
      vi.advanceTimersByTime(2_000);
    }
    const delays = onAttempt.mock.calls.map((c) => c[1]);
    expect(delays[0]).toBe(100);
    expect(delays[1]).toBe(200);
    expect(delays[2]).toBe(400);
    // Capped at 1000
    expect(delays[delays.length - 1]).toBeLessThanOrEqual(1_000);
  });
});
