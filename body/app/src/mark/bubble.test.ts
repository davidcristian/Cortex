import { describe, expect, it } from "vitest";

import { causticPath, envelopeAt, highlightsOf, lobeAt, lobePath } from "./bubble";
import type { Harmonic, Lobe } from "./bubble";

const wave = (waves: number, amplitude: number, periodSeconds = 8): Harmonic => ({
  waves,
  amplitude,
  periodSeconds,
  direction: 1,
  envelope: "steady",
});

const lobe = (over: Partial<Lobe> = {}): Lobe => ({
  cx: 50,
  cy: 50,
  r: 40,
  harmonics: [wave(2, 0.05)],
  orbit: { cx: 50, cy: 50, degrees: 0, periodSeconds: 1 },
  ...over,
});

/** Parse "M x y L x y … Z" back into points. */
function points(path: string): readonly { x: number; y: number }[] {
  const body = path.replace(/^M /u, "").replace(/ Z$/u, "");
  return body.split(" L ").map((pair) => {
    const [x, y] = pair.split(" ").map(Number);
    return { x: x ?? Number.NaN, y: y ?? Number.NaN };
  });
}

function centroid(path: string): { x: number; y: number } {
  const all = points(path);
  const sum = all.reduce((acc, point) => ({ x: acc.x + point.x, y: acc.y + point.y }), { x: 0, y: 0 });
  return { x: sum.x / all.length, y: sum.y / all.length };
}

describe("envelopeAt", () => {
  it("holds a steady harmonic at full amplitude for all time", () => {
    expect(envelopeAt("steady", 0)).toBe(1);
    expect(envelopeAt("steady", 97.3)).toBe(1);
  });

  it("crests a ping, decays it, and crests again on the next cadence", () => {
    expect(envelopeAt("ping", 0)).toBe(1);
    const mid = envelopeAt("ping", 1);
    expect(mid).toBeLessThan(0.3);
    expect(mid).toBeGreaterThan(0);
    // Well past the crest the ripple is spent, then the cadence brings it back.
    expect(envelopeAt("ping", 3.3)).toBeLessThan(0.01);
    expect(envelopeAt("ping", 3.4)).toBeCloseTo(1, 5);
  });
});

describe("lobeAt", () => {
  it("leaves a pinned lobe exactly where it is, at every instant", () => {
    const still = lobe();
    expect(lobeAt(still, 0)).toEqual({ cx: 50, cy: 50, r: 40 });
    expect(lobeAt(still, 4.2)).toEqual({ cx: 50, cy: 50, r: 40 });
  });

  it("swings an orbiting lobe about its anchor without changing its distance from it", () => {
    const rider = lobe({
      cx: 80,
      cy: 50,
      r: 12,
      orbit: { cx: 50, cy: 50, degrees: 10, periodSeconds: 8 },
    });
    const start = lobeAt(rider, 0);
    const swung = lobeAt(rider, 2);
    expect(start).toEqual({ cx: 80, cy: 50, r: 12 });
    expect(swung.cx).not.toBeCloseTo(80, 3);
    expect(Math.hypot(swung.cx - 50, swung.cy - 50)).toBeCloseTo(30, 6);
    // A full period returns it to where it started: the cluster jostles, it never drifts away.
    const later = lobeAt(rider, 8);
    expect(later.cx).toBeCloseTo(80, 6);
    expect(later.cy).toBeCloseTo(50, 6);
  });
});

describe("lobePath", () => {
  it("closes the path and honors the sample count, defaulting to a fine sampling", () => {
    const path = lobePath(lobe(), 0, 90);
    expect(path.startsWith("M ")).toBe(true);
    expect(path.endsWith(" Z")).toBe(true);
    expect(points(path)).toHaveLength(90);
    expect(points(lobePath(lobe(), 0))).toHaveLength(120);
  });

  it("keeps every point within the radius plus its harmonics' amplitudes", () => {
    const shape = lobe({ harmonics: [wave(2, 0.05), wave(3, 0.03)] });
    const radii = points(lobePath(shape, 1.7, 360)).map(({ x, y }) => Math.hypot(x - 50, y - 50));
    expect(Math.min(...radii)).toBeGreaterThanOrEqual(40 * 0.92 - 0.01);
    expect(Math.max(...radii)).toBeLessThanOrEqual(40 * 1.08 + 0.01);
    // It is genuinely off round, not a circle drawn the long way.
    expect(Math.max(...radii) - Math.min(...radii)).toBeGreaterThan(2);
  });

  it("holds the centroid still while the outline warps, which is what pins the anchor", () => {
    const shape = lobe({ harmonics: [wave(2, 0.055, 11), wave(3, 0.032, 8), wave(5, 0.011, 6)] });
    for (const seconds of [0, 1.3, 4.9, 7.2]) {
      const middle = centroid(lobePath(shape, seconds, 360));
      expect(middle.x).toBeCloseTo(50, 1);
      expect(middle.y).toBeCloseTo(50, 1);
    }
    // …and the outline really did move between those instants.
    expect(lobePath(shape, 0)).not.toBe(lobePath(shape, 1.3));
  });

  it("travels the pattern around the outline as time passes", () => {
    const shape = lobe({ harmonics: [wave(6, 0.03, 2.4)] });
    const radiusAt = (seconds: number): number => {
      const first = points(lobePath(shape, seconds, 360))[0];
      return Math.hypot((first?.x ?? 0) - 50, (first?.y ?? 0) - 50);
    };
    // One period puts the same bulge back at angle zero; part way through, a different one is
    // there. (0.1s lands on a crest for this mode; 0.6s would land on a node and prove nothing.)
    expect(radiusAt(2.4)).toBeCloseTo(radiusAt(0), 6);
    expect(radiusAt(0.1)).toBeCloseTo(40 * 1.03, 6);
    expect(radiusAt(0.1)).not.toBeCloseTo(radiusAt(0), 3);
  });

  it("scales the ping harmonic down as its crest decays", () => {
    const pinged = lobe({
      harmonics: [{ waves: 6, amplitude: 0.05, periodSeconds: 2.6, direction: 1, envelope: "ping" }],
    });
    const spread = (seconds: number): number => {
      const radii = points(lobePath(pinged, seconds, 360)).map(({ x, y }) =>
        Math.hypot(x - 50, y - 50),
      );
      return Math.max(...radii) - Math.min(...radii);
    };
    expect(spread(0)).toBeGreaterThan(3);
    expect(spread(1.5)).toBeLessThan(0.5);
  });
});

describe("highlightsOf and causticPath", () => {
  it("puts both reflections up and to the left, scaled to the lobe", () => {
    const [wash, dot] = highlightsOf({ cx: 50, cy: 50, r: 40 });
    expect(wash.cx).toBeLessThan(50);
    expect(wash.cy).toBeLessThan(50);
    expect(dot.cx).toBeLessThan(wash.cx);
    expect(dot.rx).toBeLessThan(wash.rx);
    const small = highlightsOf({ cx: 50, cy: 50, r: 10 })[0];
    expect(small.rx).toBeCloseTo(wash.rx / 4, 6);
  });

  it("draws the caustic as an arc on the far side, scaled to the lobe", () => {
    const arc = causticPath({ cx: 50, cy: 50, r: 40 });
    expect(arc).toMatch(/^M [\d.]+ [\d.]+ A 31\.20 31\.20 0 0 1 [\d.]+ [\d.]+$/u);
    expect(causticPath({ cx: 50, cy: 50, r: 10 })).toContain("A 7.80 7.80");
  });
});
