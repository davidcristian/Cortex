import { describe, expect, it } from "vitest";

import { relativeTime } from "./relativeTime";

const NOW = 1_000_000_000_000;

describe("relativeTime", () => {
  it("reads under a minute as 'just now'", () => {
    expect(relativeTime(NOW - 30_000, NOW)).toBe("just now");
  });

  it("reads minutes, hours, and days", () => {
    expect(relativeTime(NOW - 5 * 60_000, NOW)).toBe("5m ago");
    expect(relativeTime(NOW - 3 * 60 * 60_000, NOW)).toBe("3h ago");
    expect(relativeTime(NOW - 2 * 24 * 60 * 60_000, NOW)).toBe("2d ago");
  });

  it("clamps a future timestamp to 'just now'", () => {
    expect(relativeTime(NOW + 10_000, NOW)).toBe("just now");
  });

  it("says one of four things, which is what the switcher's time column is sized to", () => {
    // `.switcher-time` reserves 55px so the column does not move while the clock runs, and 55 is a
    // measurement of these four shapes at that size: `just now` 48.4, `59m ago` 50.9 (the widest
    // bounded one), `23h ago` 47, and the day branch, which is unbounded, at 47 for two digits and
    // 54.3 for three. A fifth shape, or a longer word in one of these, means re-measuring that
    // number rather than adding a string, which is why this test covers the whole range rather than
    // samples.
    const shapes = /^(just now|[1-9]\d*[mhd] ago)$/u;
    const minute = 60_000;
    const spans = [0, 1, 59, 60, 61, 1439, 1440, 1441, 60 * 24 * 999, 60 * 24 * 9999];
    for (const minutes of spans) {
      expect(relativeTime(NOW - minutes * minute, NOW)).toMatch(shapes);
    }
    // The two shapes the width was measured from, exactly as measured.
    expect(relativeTime(NOW - 59 * minute, NOW)).toBe("59m ago");
    expect(relativeTime(NOW - 999 * 24 * 60 * minute, NOW)).toBe("999d ago");
  });
});
