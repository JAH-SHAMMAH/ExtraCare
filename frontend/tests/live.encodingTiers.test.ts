import { describe, it, expect } from "vitest";
import {
  paramsForTier,
  paramsForViewerCount,
  tierForViewerCount,
} from "@/lib/live/encodingTiers";

describe("encodingTiers.tierForViewerCount", () => {
  it("starts at hd for small classes", () => {
    expect(tierForViewerCount(1)).toBe("hd");
    expect(tierForViewerCount(5)).toBe("hd");
  });

  it("drops to sd past 5 viewers", () => {
    expect(tierForViewerCount(6)).toBe("sd");
    expect(tierForViewerCount(15)).toBe("sd");
  });

  it("drops to low past 15 viewers", () => {
    expect(tierForViewerCount(16)).toBe("low");
    expect(tierForViewerCount(30)).toBe("low");
  });

  it("falls back to audio past 30 viewers", () => {
    expect(tierForViewerCount(31)).toBe("audio");
    expect(tierForViewerCount(100)).toBe("audio");
  });
});

describe("encodingTiers.paramsForTier", () => {
  it("hd has full bitrate and native resolution", () => {
    const p = paramsForTier("hd");
    expect(p.maxBitrate).toBe(1_500_000);
    expect(p.scaleResolutionDownBy).toBe(1);
    expect(p.audioOnly).toBe(false);
  });

  it("audio tier disables video", () => {
    const p = paramsForTier("audio");
    expect(p.audioOnly).toBe(true);
    expect(p.maxBitrate).toBe(0);
  });

  it("bitrate monotonically decreases from hd → audio", () => {
    const tiers = ["hd", "sd", "low", "audio"] as const;
    const bitrates = tiers.map((t) => paramsForTier(t).maxBitrate);
    for (let i = 1; i < bitrates.length; i++) {
      expect(bitrates[i]).toBeLessThan(bitrates[i - 1]);
    }
  });
});

describe("encodingTiers.paramsForViewerCount", () => {
  it("chains tier selection and params lookup", () => {
    expect(paramsForViewerCount(3).audioOnly).toBe(false);
    expect(paramsForViewerCount(50).audioOnly).toBe(true);
  });
});
