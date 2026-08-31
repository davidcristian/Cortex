import { describe, expect, it } from "vitest";

import { EDGES, LUCID, REVERIE, STILL, TRANCE, resolveEdge } from "./edges";
import { BLEED, reachOf } from "./liquid";

describe("resolveEdge", () => {
  it("defaults to Lucid with no preference, since a fresh overlay breathes", () => {
    expect(resolveEdge(null)).toBe(LUCID);
  });

  it("returns the named style for every style in the registry", () => {
    for (const edge of EDGES) {
      expect(resolveEdge(edge.name)).toBe(edge);
    }
  });

  it("falls back to the default when the preference names no known style", () => {
    expect(resolveEdge("dreamier-deluxe")).toBe(LUCID);
  });
});

describe("EDGES", () => {
  it("names every style uniquely, since the name is what a preference stores", () => {
    expect(new Set(EDGES.map((edge) => edge.name)).size).toBe(EDGES.length);
  });

  it("labels and describes every style, since the picker shows both", () => {
    for (const edge of EDGES) {
      expect(edge.label.length).toBeGreaterThan(0);
      expect(edge.note.length).toBeGreaterThan(0);
    }
  });

  it("ships the ladder in its order, Still to Trance, because the order is the explanation", () => {
    expect(EDGES.map((edge) => edge.name)).toEqual(["still", "lucid", "reverie", "trance"]);
  });

  it("keeps Still genuinely still: no waves, no glow, nothing left to deepen", () => {
    expect(STILL.waves).toHaveLength(0);
    expect(STILL.glow).toBe("none");
    expect(reachOf(STILL)).toBe(0);
  });

  it("uses only integer wave orders of two or higher, which close the loop and pin the centre", () => {
    // A non-integer order tears the outline at its seam, and an order of one would translate the
    // whole window, so both are refused however a style is otherwise tuned.
    for (const edge of EDGES) {
      for (const wave of edge.waves) {
        expect(Number.isInteger(wave.waves)).toBe(true);
        expect(wave.waves).toBeGreaterThanOrEqual(2);
        expect(wave.periodSeconds).toBeGreaterThan(0);
      }
    }
  });

  it("bounds every style's reach under the bleed, which is what keeps the waves in the wrapper", () => {
    for (const edge of EDGES) {
      expect(reachOf(edge)).toBeLessThanOrEqual(BLEED);
      expect(edge.edgeShare).toBeGreaterThanOrEqual(0);
      expect(edge.edgeShare).toBeLessThanOrEqual(1);
      expect(edge.depthBoost).toBeGreaterThanOrEqual(0);
    }
  });

  it("gives Reverie exactly Lucid's liquid, so the glow is the whole difference", () => {
    expect(REVERIE.waves).toEqual(LUCID.waves);
    expect(REVERIE.edgeShare).toBe(LUCID.edgeShare);
    expect(REVERIE.depthBoost).toBe(LUCID.depthBoost);
    // The glow is the only difference between the two: Lucid adds no colour at all. This assertion
    // is what caught them shipping identical in the first visual pass.
    expect(LUCID.glow).toBe("none");
    expect(REVERIE.glow).toBe("settled");
    expect(TRANCE.glow).toBe("ember");
  });
});
