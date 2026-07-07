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
});
