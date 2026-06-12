import { describe, it, expect } from "vitest";
import {
  sortParticipants,
  type ParticipantInfo,
} from "@/components/live/ParticipantsPanel";

function p(overrides: Partial<ParticipantInfo>): ParticipantInfo {
  return {
    user_id: overrides.user_id ?? "u",
    name: overrides.name ?? "Name",
    handRaised: overrides.handRaised ?? false,
    muted: overrides.muted ?? false,
    speaking: overrides.speaking,
  };
}

describe("ParticipantsPanel.sortParticipants", () => {
  it("places hand-raised participants first", () => {
    const result = sortParticipants([
      p({ user_id: "a", name: "Alice", handRaised: false }),
      p({ user_id: "b", name: "Bob", handRaised: true }),
      p({ user_id: "c", name: "Cara", handRaised: false }),
    ]);
    expect(result[0].user_id).toBe("b");
  });

  it("sorts alphabetically within each hand group", () => {
    const result = sortParticipants([
      p({ user_id: "c", name: "Cara", handRaised: true }),
      p({ user_id: "b", name: "Bob", handRaised: true }),
      p({ user_id: "z", name: "Zoe", handRaised: false }),
      p({ user_id: "a", name: "Alice", handRaised: false }),
    ]);
    expect(result.map((x) => x.user_id)).toEqual(["b", "c", "a", "z"]);
  });

  it("returns a new array (does not mutate input)", () => {
    const list = [
      p({ user_id: "a", name: "Alice", handRaised: false }),
      p({ user_id: "b", name: "Bob", handRaised: true }),
    ];
    const original = list.map((x) => x.user_id);
    sortParticipants(list);
    expect(list.map((x) => x.user_id)).toEqual(original);
  });

  it("handles an empty list", () => {
    expect(sortParticipants([])).toEqual([]);
  });
});
