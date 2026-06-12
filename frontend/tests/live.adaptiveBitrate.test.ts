import { describe, it, expect } from "vitest";
import {
  createAdaptiveState,
  recommendTier,
  sampleFromStats,
  updateTierWithHysteresis,
  type NetworkSample,
} from "@/lib/live/adaptiveBitrate";

function healthy(): NetworkSample {
  return { packetLossPct: 0.5, rttMs: 60, timestamp: Date.now() };
}

function mildBad(): NetworkSample {
  return { packetLossPct: 3, rttMs: 250, timestamp: Date.now() };
}

function badNetwork(): NetworkSample {
  return { packetLossPct: 7, rttMs: 500, timestamp: Date.now() };
}

function awful(): NetworkSample {
  return { packetLossPct: 20, rttMs: 1000, timestamp: Date.now() };
}

describe("adaptiveBitrate.recommendTier", () => {
  it("keeps hd on a healthy link", () => {
    expect(recommendTier(healthy(), "hd")).toBe("hd");
  });

  it("downgrades hd → sd on mild loss", () => {
    expect(recommendTier(mildBad(), "hd")).toBe("sd");
  });

  it("drops to low on elevated loss", () => {
    expect(recommendTier(badNetwork(), "sd")).toBe("low");
  });

  it("falls to audio on unusable links", () => {
    expect(recommendTier(awful(), "hd")).toBe("audio");
    expect(recommendTier(awful(), "sd")).toBe("audio");
    expect(recommendTier(awful(), "low")).toBe("audio");
  });

  it("recovers up one step on sustained health", () => {
    expect(recommendTier(healthy(), "audio")).toBe("low");
    expect(recommendTier(healthy(), "low")).toBe("sd");
    expect(recommendTier(healthy(), "sd")).toBe("hd");
  });
});

describe("adaptiveBitrate.updateTierWithHysteresis", () => {
  it("does not downgrade on a single bad sample", () => {
    const state = createAdaptiveState("hd");
    const tier = updateTierWithHysteresis(state, mildBad());
    expect(tier).toBe("hd");
    expect(state.consecutiveBad).toBe(1);
  });

  it("downgrades once downThreshold bad samples accumulate", () => {
    const state = createAdaptiveState("hd");
    updateTierWithHysteresis(state, mildBad());
    const tier = updateTierWithHysteresis(state, mildBad(), { downThreshold: 2 });
    expect(tier).toBe("sd");
    expect(state.currentTier).toBe("sd");
  });

  it("does not upgrade on a single good sample", () => {
    const state = createAdaptiveState("low");
    const tier = updateTierWithHysteresis(state, healthy(), { upThreshold: 4 });
    expect(tier).toBe("low");
    expect(state.consecutiveGood).toBe(1);
  });

  it("upgrades after upThreshold consecutive healthy samples", () => {
    const state = createAdaptiveState("low");
    for (let i = 0; i < 3; i++) updateTierWithHysteresis(state, healthy(), { upThreshold: 4 });
    expect(state.currentTier).toBe("low");
    const tier = updateTierWithHysteresis(state, healthy(), { upThreshold: 4 });
    expect(tier).toBe("sd");
  });

  it("resets counters when direction reverses", () => {
    const state = createAdaptiveState("hd");
    updateTierWithHysteresis(state, mildBad());
    expect(state.consecutiveBad).toBe(1);
    updateTierWithHysteresis(state, healthy());
    // healthy from hd stays hd, so counters should be zero (no direction)
    expect(state.consecutiveBad).toBe(0);
    expect(state.consecutiveGood).toBe(0);
  });
});

describe("adaptiveBitrate.sampleFromStats", () => {
  function makeReport(entries: any[]): RTCStatsReport {
    return {
      forEach: (cb: (v: any) => void) => entries.forEach(cb),
    } as unknown as RTCStatsReport;
  }

  it("returns null when no outbound video rtp is present", () => {
    const state = createAdaptiveState("hd");
    const rep = makeReport([{ type: "candidate-pair", state: "succeeded", nominated: true }]);
    expect(sampleFromStats(rep, state)).toBeNull();
  });

  it("computes loss percentage from packet deltas", () => {
    const state = createAdaptiveState("hd");
    // First poll primes baseline
    const first = makeReport([
      { type: "outbound-rtp", kind: "video", packetsSent: 100 },
      { type: "remote-inbound-rtp", kind: "video", packetsLost: 0, roundTripTime: 0.1 },
    ]);
    const s1 = sampleFromStats(first, state);
    expect(s1).not.toBeNull();
    expect(s1!.packetLossPct).toBe(0);
    // Second poll: +100 sent, +5 lost → 5/105 ≈ 4.76%
    const second = makeReport([
      { type: "outbound-rtp", kind: "video", packetsSent: 200 },
      { type: "remote-inbound-rtp", kind: "video", packetsLost: 5, roundTripTime: 0.1 },
    ]);
    const s2 = sampleFromStats(second, state);
    expect(s2!.packetLossPct).toBeGreaterThan(4);
    expect(s2!.packetLossPct).toBeLessThan(5);
    expect(s2!.rttMs).toBe(100);
  });
});
