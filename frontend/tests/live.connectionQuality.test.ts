import { describe, it, expect } from "vitest";
import { describeConnection } from "@/lib/live/connectionQuality";

describe("connectionQuality.describeConnection", () => {
  it("returns connecting when not yet connected and no retries", () => {
    const r = describeConnection({ connected: false, reconnectAttempts: 0, tier: null });
    expect(r.level).toBe("connecting");
    expect(r.tone).toBe("neutral");
  });

  it("prioritises reconnecting over everything else", () => {
    const r = describeConnection({ connected: true, reconnectAttempts: 2, tier: "hd" });
    expect(r.level).toBe("reconnecting");
    expect(r.tone).toBe("poor");
  });

  it("hd tier reads as good", () => {
    const r = describeConnection({ connected: true, reconnectAttempts: 0, tier: "hd" });
    expect(r.level).toBe("good");
    expect(r.tone).toBe("good");
  });

  it("sd tier reads as fair", () => {
    const r = describeConnection({ connected: true, reconnectAttempts: 0, tier: "sd" });
    expect(r.level).toBe("fair");
  });

  it("low tier reads as poor", () => {
    const r = describeConnection({ connected: true, reconnectAttempts: 0, tier: "low" });
    expect(r.level).toBe("poor");
    expect(r.tone).toBe("poor");
  });

  it("audio tier surfaces the audio-only label", () => {
    const r = describeConnection({ connected: true, reconnectAttempts: 0, tier: "audio" });
    expect(r.level).toBe("audio-only");
    expect(r.label).toBe("Audio only");
  });

  it("connected without a tier falls back to generic connected state", () => {
    const r = describeConnection({ connected: true, reconnectAttempts: 0, tier: null });
    expect(r.level).toBe("good");
    expect(r.label).toBe("Connected");
  });

  it("always produces a human description for screen readers / tooltips", () => {
    const cases = [
      { connected: false, reconnectAttempts: 0, tier: null },
      { connected: true, reconnectAttempts: 1, tier: "sd" as const },
      { connected: true, reconnectAttempts: 0, tier: "audio" as const },
    ];
    for (const c of cases) {
      const r = describeConnection(c);
      expect(r.description.length).toBeGreaterThan(0);
    }
  });
});
