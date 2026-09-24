import { describe, expect, it } from "vitest";
import { nextFace } from "./cardFace";
import { pickNextIndex, rollDieFace } from "./random";

describe("pickNextIndex", () => {
  it("never returns the current index", () => {
    for (let current = 0; current < 5; current++) {
      for (const r of [0, 0.2, 0.5, 0.79, 0.9999]) {
        const next = pickNextIndex(5, current, () => r);
        expect(next).not.toBe(current);
        expect(next).toBeGreaterThanOrEqual(0);
        expect(next).toBeLessThan(5);
      }
    }
  });

  it("can reach every other index", () => {
    const seen = new Set<number>();
    for (let i = 0; i < 4; i++) seen.add(pickNextIndex(5, 2, () => i / 4));
    expect([...seen].sort()).toEqual([0, 1, 3, 4]);
  });

  it("returns 0 when there is only one option", () => {
    expect(pickNextIndex(1, 0, () => 0.7)).toBe(0);
  });
});

describe("rollDieFace", () => {
  it("maps the rng range onto 1–6", () => {
    expect(rollDieFace(() => 0)).toBe(1);
    expect(rollDieFace(() => 0.5)).toBe(4);
    expect(rollDieFace(() => 0.9999)).toBe(6);
  });
});

describe("nextFace", () => {
  it("cycles subject → prompt → example → subject", () => {
    expect(nextFace("subject")).toBe("prompt");
    expect(nextFace("prompt")).toBe("example");
    expect(nextFace("example")).toBe("subject");
  });
});
