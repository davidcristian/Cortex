import { describe, expect, it, vi } from "vitest";

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
  lettersOf,
  pxOr,
  rampAt,
  tokenize,
} from "./front";

describe("advance", () => {
  it("sprints a deep backlog at the capped pace, easing the velocity toward it", () => {
    const one = advance(RESTING_FRONT, 100, 0.016);
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
    expect(one.velocity).toBeCloseTo(20 / 0.35, 5);
  });

  it("stops at the goal and aims at nothing beyond it", () => {
    const arrived = advance({ at: 5, velocity: 150 }, 5, 0.016);
    expect(arrived.at).toBe(5);
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

const words = (content: string) => tokenize(content).tokens;

const MIXED =
  "Cafe\u0301  ok 👍🏽👨\u200d👩\u200d👧🇷🇴🇬\r\nשָׁלוֹם עולם\tनमस्ते 한국어 " +
  "a".repeat(CHUNK_LETTERS + 3) +
  "e\u0301" +
  "🇷🇴".repeat(CHUNK_LETTERS) +
  "\n\n" +
  "مرحبا";

describe("tokenize", () => {
  it("lays words as boxes holding their letters and whitespace verbatim, newlines included", () => {
    expect(words("Quiet  morning.\n\nDone")).toEqual([
      { kind: "word", text: "Quiet", letters: [..."Quiet"] },
      { kind: "gap", text: "  " },
      { kind: "word", text: "morning.", letters: [..."morning."] },
      { kind: "gap", text: "\n\n" },
      { kind: "word", text: "Done", letters: [..."Done"] },
    ]);
  });

  it("survives leading whitespace and an empty reply", () => {
    expect(words(" x")).toEqual([
      { kind: "gap", text: " " },
      { kind: "word", text: "x", letters: ["x"] },
    ]);
    expect(tokenize("")).toEqual({ content: "", tokens: [] });
  });

  it("chunks a giant run so the bubble can still break a streamed hash", () => {
    const hash = "a".repeat(CHUNK_LETTERS * 2 + 12);
    expect(words(hash).map((t) => t.text.length)).toEqual([CHUNK_LETTERS, CHUNK_LETTERS, 12]);
  });

  it("chunks by letter, never through a surrogate pair or a flag", () => {
    const tokens = words("🇷🇴".repeat(CHUNK_LETTERS + 1));
    expect(tokens.map((t) => (t.kind === "word" ? t.letters.length : 0))).toEqual([
      CHUNK_LETTERS,
      1,
    ]);
    expect(tokens.every((t) => t.kind === "word" && t.letters.every((p) => p === "🇷🇴"))).toBe(
      true,
    );
  });

  it("extends the last render's tokens to the same tokens a fresh split lays", () => {
    for (const step of [1, 2, 3, 5, 7]) {
      let made = tokenize("");
      for (let end = step; end < MIXED.length + step; end += step) {
        const content = MIXED.slice(0, end);
        made = tokenize(content, made);
        expect(made).toEqual(tokenize(content));
      }
    }
  });

  it("keeps every token object but the last, and splits only the growing word", () => {
    const head = `${"שָׁלוֹם ".repeat(40)}עול`;
    const before = tokenize(head);
    const segment = vi.spyOn(Intl.Segmenter.prototype, "segment");
    try {
      const after = tokenize(`${head}ם`, before);
      expect(after.tokens.slice(0, -1)).toEqual(before.tokens.slice(0, -1));
      expect(after.tokens.slice(0, -1).every((t, i) => t === before.tokens[i])).toBe(true);
      expect(segment.mock.calls).toEqual([["עולם"]]);
    } finally {
      segment.mockRestore();
    }
  });

  it("splits afresh when the text no longer extends the last render's", () => {
    expect(tokenize("one two", tokenize("uno two"))).toEqual(tokenize("one two"));
    expect(tokenize("ab", tokenize("ab cd"))).toEqual(tokenize("ab"));
  });

  it("splits afresh after a cut inside a surrogate pair, which the next text completes", () => {
    const run = `${"a".repeat(CHUNK_LETTERS - 1)}👍`;
    const open = tokenize(`${run}\uD83C`);
    expect(open.tokens.map((t) => t.text)).toEqual([run, "\uD83C"]);
    expect(tokenize(`${run}🏽`, open)).toEqual(tokenize(`${run}🏽`));
    expect(words(`${run}🏽`)).toHaveLength(1);
  });
});

describe("lettersOf", () => {
  it("keeps an accent, a flag, a skin tone and a family emoji each one letter", () => {
    const text = "Cafe\u0301 🇷🇴👍🏽👨\u200d👩\u200d👧 שָׁלוֹם";
    expect(lettersOf(text)).toEqual([
      ..."Caf",
      "e\u0301",
      " ",
      "🇷🇴",
      "👍🏽",
      "👨\u200d👩\u200d👧",
      " ",
      "שָׁ",
      "ל",
      "וֹ",
      "ם",
    ]);
  });

  it("splits text below U+0300 by code point without the segmenter, CR LF kept one letter", () => {
    const below = Array.from({ length: 0x300 }, (_, point) => String.fromCodePoint(point))
      .filter((letter) => letter !== "\r")
      .join("");
    const segment = vi.spyOn(Intl.Segmenter.prototype, "segment");
    try {
      expect(lettersOf(below)).toEqual([...below]);
      expect(segment).not.toHaveBeenCalled();
      expect(lettersOf("a\r\nb")).toEqual(["a", "\r\n", "b"]);
      expect(lettersOf("Cafe\u0301")).toEqual([..."Caf", "e\u0301"]);
      expect(lettersOf("ok👍🏽")).toEqual(["o", "k", "👍🏽"]);
      expect(segment).toHaveBeenCalledTimes(3);
    } finally {
      segment.mockRestore();
    }
  });
});

describe("letterCountOf and confirmedOf", () => {
  it("counts word letters only; gaps are text nodes, not letters", () => {
    expect(letterCountOf(words("hi there "))).toBe(7);
  });

  it("holds a trailing word out of the confirmed count, because it can still grow", () => {
    expect(confirmedOf(words("hi ther"))).toBe(2);
  });

  it("confirms everything once whitespace completes the last word", () => {
    expect(confirmedOf(words("hi there "))).toBe(7);
  });

  it("confirms nothing of an empty reply", () => {
    expect(confirmedOf(words(""))).toBe(0);
  });

  it("counts a flag or a family emoji as one letter, confirmed or still growing", () => {
    expect(letterCountOf(words("🇷🇴 👨\u200d👩\u200d👧 "))).toBe(2);
    expect(confirmedOf(words("🇷🇴 👍🏽"))).toBe(1);
  });
});
