import { describe, expect, it } from "vitest";
import { rollDieFace } from "./random";

describe("rollDieFace", () => {
  it("maps the rng range onto 1–6", () => {
    expect(rollDieFace(() => 0)).toBe(1);
    expect(rollDieFace(() => 0.5)).toBe(4);
    expect(rollDieFace(() => 0.9999)).toBe(6);
  });
});
