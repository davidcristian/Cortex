import { describe, expect, it } from "vitest";

import { MARKS, MULL, resolveMark } from "./marks";

describe("resolveMark", () => {
  it("defaults to Mull with no preference", () => {
    expect(resolveMark(null)).toBe(MULL);
  });

  it("returns the named style for every style in the registry", () => {
    for (const mark of MARKS) {
      expect(resolveMark(mark.name)).toBe(mark);
    }
  });

  it("falls back to the default when the preference names no known style", () => {
    expect(resolveMark("bubbles-deluxe")).toBe(MULL);
  });
});

describe("MARKS", () => {
  it("names every style uniquely, since the name is what a preference stores", () => {
    expect(new Set(MARKS.map((mark) => mark.name)).size).toBe(MARKS.length);
  });

  it("labels and describes every style, since the picker shows both", () => {
    for (const mark of MARKS) {
      expect(mark.label.length).toBeGreaterThan(0);
      expect(mark.note.length).toBeGreaterThan(0);
    }
  });

  it("uses only harmonics of order two or higher, which is what pins the anchor", () => {
    // An n=1 term translates the whole outline: the mark would wander in its corner, which the
    // design forbids. Everything else about a style is taste; this is the invariant.
    for (const mark of MARKS) {
      for (const lobe of mark.lobes) {
        for (const harmonic of lobe.harmonics) {
          expect(harmonic.waves).toBeGreaterThanOrEqual(2);
        }
      }
    }
  });

  it("keeps every lobe inside the mark's own box, so nothing clips at the corner", () => {
    for (const mark of MARKS) {
      for (const lobe of mark.lobes) {
        const reach = lobe.r * 1.1;
        expect(lobe.cx - reach).toBeGreaterThanOrEqual(0);
        expect(lobe.cy - reach).toBeGreaterThanOrEqual(0);
        expect(lobe.cx + reach).toBeLessThanOrEqual(100);
        expect(lobe.cy + reach).toBeLessThanOrEqual(100);
      }
    }
  });
});
