import { describe, expect, it } from "vitest";

import {
  BAND_LETTERS,
  CHUNK_LETTERS,
  MAX_PACE,
  MIN_PACE,
  RESTING_FRONT,
  advance,
  approach,
  confirmedOf,
  goalOf,
  letterCountOf,
  pxOr,
  rampAt,
  tokenize,
} from "./front";

describe("advance", () => {
  it("sprints a deep backlog at the capped pace, easing the velocity toward it", () => {
    const one = advance(RESTING_FRONT, 100, 0.016);
    // A backlog of 100 implies 100 / 0.35 ~ 286 letters/s; the cap holds it to MAX_PACE, and the
    // velocity blends toward that rather than jumping.
    expect(one.velocity).toBeCloseTo(MAX_PACE * 0.016 * 6, 5);
    expect(one.at).toBeCloseTo(one.velocity * 0.016, 5);
  });

  it("crawls a shallow backlog at the floor, so the tail never stalls", () => {
    const front = { at: 0, velocity: MIN_PACE };
    const one = advance(front, 1, 0.016);
    expect(one.velocity).toBeCloseTo(MIN_PACE, 5);
  });

  it("runs an in-between backlog at exactly what it warrants", () => {
    const front = { at: 0, velocity: 0 };
    const one = advance(front, 20, 1 / 6);
    // 20 letters over 0.35s is ~57/s, inside both clamps; dt * gain is exactly 1 here, so the
    // velocity lands on the target in one step (the saturated blend).
    expect(one.velocity).toBeCloseTo(20 / 0.35, 5);
  });

  it("stops at the goal and aims at nothing beyond it", () => {
    const arrived = advance({ at: 5, velocity: 150 }, 5, 0.016);
    expect(arrived.at).toBe(5);
    // Backlog is zero, so the target pace is zero and the velocity decays.
    expect(arrived.velocity).toBeLessThan(150);
  });

  it("caps one frame's travel at the goal instead of overshooting", () => {
    const one = advance({ at: 0, velocity: 150 }, 1, 0.05);
    expect(one.at).toBe(1);
  });

  it("never moves backward when it starts past the goal (the remount snap)", () => {
    const held = advance({ at: 15, velocity: 0 }, 6, 0.05);
    expect(held.at).toBe(15);
  });
});

describe("goalOf", () => {
  it("aims at the confirmed letters while the turn streams", () => {
    expect(goalOf(12, 7, false)).toBe(7);
  });

  it("never aims past the letters actually laid", () => {
    expect(goalOf(5, 9, false)).toBe(5);
  });

  it("overshoots by one whole band on the drain, so the tail solidifies", () => {
    expect(goalOf(12, 7, true)).toBe(12 + BAND_LETTERS);
  });
});

describe("rampAt", () => {
  it("holds a letter the front has not reached at zero", () => {
    expect(rampAt(3, 3)).toBe(0);
    expect(rampAt(3, 7)).toBe(0);
  });

  it("finishes a letter a whole band behind the front", () => {
    expect(rampAt(BAND_LETTERS + 2, 2)).toBe(1);
  });

  it("smoothsteps the letters inside the band", () => {
    // Halfway through the band is exactly half condensed, with no corner at either end.
    expect(rampAt(BAND_LETTERS / 2, 0)).toBeCloseTo(0.5, 5);
    expect(rampAt(2, 0)).toBeGreaterThan(0);
    expect(rampAt(2, 0)).toBeLessThan(0.5);
  });
});

describe("approach", () => {
  it("moves a fraction of the distance per frame", () => {
    expect(approach(0, 100, 0.016, 10)).toBeCloseTo(16, 5);
  });

  it("saturates at the target rather than oscillating past it", () => {
    expect(approach(0, 100, 0.5, 10)).toBe(100);
  });
});

describe("pxOr", () => {
  it("reads a pixel length", () => {
    expect(pxOr("22.475px", 5)).toBeCloseTo(22.475, 5);
  });

  it("falls back when the engine offers nothing (jsdom answers empty)", () => {
    expect(pxOr("", 22.5)).toBe(22.5);
  });

  it("rejects a unitless line-height's multiplier, which would pose a 2px-tall box", () => {
    expect(pxOr("1.55", 22.5)).toBe(22.5);
  });
});

describe("tokenize", () => {
  it("lays words as boxes and whitespace verbatim, newlines included", () => {
    expect(tokenize("Quiet  morning.\n\nDone")).toEqual([
      { kind: "word", text: "Quiet" },
      { kind: "gap", text: "  " },
      { kind: "word", text: "morning." },
      { kind: "gap", text: "\n\n" },
      { kind: "word", text: "Done" },
    ]);
  });

  it("survives leading whitespace and an empty reply", () => {
    expect(tokenize(" x")).toEqual([
      { kind: "gap", text: " " },
      { kind: "word", text: "x" },
    ]);
    expect(tokenize("")).toEqual([]);
  });

  it("chunks a giant run so the bubble can still break a streamed hash", () => {
    const hash = "a".repeat(CHUNK_LETTERS * 2 + 12);
    expect(tokenize(hash).map((t) => t.text.length)).toEqual([
      CHUNK_LETTERS,
      CHUNK_LETTERS,
      12,
    ]);
  });

  it("chunks by code point, never through a surrogate pair", () => {
    const smileys = "🙂".repeat(CHUNK_LETTERS + 1);
    const tokens = tokenize(smileys);
    expect(tokens.map((t) => [...t.text].length)).toEqual([CHUNK_LETTERS, 1]);
    // Every chunk still holds whole smileys, not broken halves.
    expect(tokens.every((t) => [...t.text].every((p) => p === "🙂"))).toBe(true);
  });
});

describe("letterCountOf and confirmedOf", () => {
  it("counts word letters only; gaps are text nodes, not letters", () => {
    expect(letterCountOf(tokenize("hi there "))).toBe(7);
  });

  it("holds a trailing word out of the confirmed count, because it can still grow", () => {
    expect(confirmedOf(tokenize("hi ther"))).toBe(2);
  });

  it("confirms everything once whitespace completes the last word", () => {
    expect(confirmedOf(tokenize("hi there "))).toBe(7);
  });

  it("confirms nothing of an empty reply", () => {
    expect(confirmedOf(tokenize(""))).toBe(0);
  });
});
