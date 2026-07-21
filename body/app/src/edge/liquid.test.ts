import { describe, expect, it } from "vitest";

import { LUCID, STILL, TRANCE } from "./edges";
import { BLEED, CORNER_RADIUS, approachDepth, edgePath, reachOf } from "./liquid";

/** Every vertex of a sampled path, read back out of the string. */
function pointsOf(path: string): readonly (readonly [number, number])[] {
  return [...path.matchAll(/[ML](-?[\d.]+) (-?[\d.]+)/gu)].map((hit) => [
    Number(hit[1]),
    Number(hit[2]),
  ]);
}

describe("edgePath", () => {
  it("closes the loop and never repeats itself, being a pure function of its arguments", () => {
    const path = edgePath(LUCID, 560, 480, 3.2, 0);
    expect(path.startsWith("M")).toBe(true);
    expect(path.endsWith("Z")).toBe(true);
    expect(edgePath(LUCID, 560, 480, 3.2, 0)).toBe(path);
  });

  it("holds Still perfectly still: one rounded rectangle, whatever the clock says", () => {
    const early = edgePath(STILL, 560, 480, 0, 0);
    expect(edgePath(STILL, 560, 480, 99.7, 1)).toBe(early);
    expect(early).toContain(`A${CORNER_RADIUS} ${CORNER_RADIUS}`);
    // The neutral line sits exactly one bleed inside the wrapper, which the component aligns
    // with the panel's own border: the liquid breathes around the REGULAR edge, not inside it.
    expect(early.startsWith(`M${BLEED + CORNER_RADIUS} ${BLEED}`)).toBe(true);
  });

  it("moves a liquid with the clock and deepens it with the working depth", () => {
    const rest = edgePath(LUCID, 560, 480, 1, 0);
    expect(edgePath(LUCID, 560, 480, 2, 0)).not.toBe(rest);
    expect(edgePath(LUCID, 560, 480, 1, 1)).not.toBe(rest);
  });

  it("never leaves the box, which is the invariant the panel's layout relies on", () => {
    // Swept rather than spot-checked: amplitudes, weights and the depth scale are constructed to
    // bound the displacement by the reach the outline is inset by, and this is that proof run.
    for (const style of [LUCID, TRANCE]) {
      for (const seconds of [0, 1.7, 6.3, 21.9]) {
        for (const depth of [0, 0.5, 1]) {
          for (const [x, y] of pointsOf(edgePath(style, 560, 480, seconds, depth))) {
            expect(x).toBeGreaterThanOrEqual(0);
            expect(x).toBeLessThanOrEqual(560);
            expect(y).toBeGreaterThanOrEqual(0);
            expect(y).toBeLessThanOrEqual(480);
          }
        }
      }
    }
  });

  it("keeps a scaled miniature inside its own box the same way", () => {
    for (const [x, y] of pointsOf(edgePath(TRANCE, 72, 50, 4.6, 0, 0.32))) {
      expect(x).toBeGreaterThanOrEqual(0);
      expect(x).toBeLessThanOrEqual(72);
      expect(y).toBeGreaterThanOrEqual(0);
      expect(y).toBeLessThanOrEqual(50);
    }
  });

  it("falls back to the plain rectangle when the box cannot carry the liquid", () => {
    // A width too small for two arcs and a run, then a height: both are start-up and test-DOM
    // shapes (a zero-size box before the first layout), not error states, so they draw calmly.
    expect(edgePath(LUCID, 80, 480, 1, 0)).toContain("A");
    expect(edgePath(LUCID, 560, 80, 1, 0)).toContain("A");
    // Smaller than its own inset, the box degenerates to a point rather than negative arcs.
    expect(edgePath(LUCID, 10, 10, 1, 0)).toContain("H");
  });

  it("prices the worst case with the reach, resting spectrum times the working boost", () => {
    expect(reachOf(LUCID)).toBeCloseTo(8.5 * 1.38, 5);
    expect(reachOf(STILL)).toBe(0);
  });
});

describe("approachDepth", () => {
  it("closes on the target without overshooting, whatever the frame spacing", () => {
    const one = approachDepth(0, 1, 0.28);
    expect(one).toBeGreaterThan(0.5);
    expect(one).toBeLessThan(1);
    expect(approachDepth(0, 1, 10)).toBeCloseTo(1, 5);
    expect(approachDepth(1, 0, 10)).toBeCloseTo(0, 5);
  });

  it("stays put at the target and on a frame that took no time", () => {
    expect(approachDepth(0.5, 0.5, 0.1)).toBe(0.5);
    expect(approachDepth(0.3, 1, 0)).toBe(0.3);
    expect(approachDepth(0.3, 1, -1)).toBe(0.3);
  });
});
