import { describe, expect, it } from "vitest";

import { nextTab } from "./tabStrip";

const STRIP = ["face", "chords", "voice"] as const;

describe("nextTab", () => {
  it("walks right along the strip and wraps off the end", () => {
    expect(nextTab("ArrowRight", STRIP, "face")).toBe("chords");
    expect(nextTab("ArrowRight", STRIP, "chords")).toBe("voice");
    expect(nextTab("ArrowRight", STRIP, "voice")).toBe("face");
  });

  it("walks left along the strip and wraps off the front", () => {
    expect(nextTab("ArrowLeft", STRIP, "voice")).toBe("chords");
    expect(nextTab("ArrowLeft", STRIP, "chords")).toBe("face");
    expect(nextTab("ArrowLeft", STRIP, "face")).toBe("voice");
  });

  it("sends Home and End to the ends, from anywhere, without wrapping past them", () => {
    expect(nextTab("Home", STRIP, "voice")).toBe("face");
    expect(nextTab("Home", STRIP, "chords")).toBe("face");
    expect(nextTab("End", STRIP, "voice")).toBe("voice");
    expect(nextTab("Home", STRIP, "face")).toBe("face");
  });

  it("leaves every other key alone, the vertical arrows included", () => {
    expect(nextTab("ArrowDown", STRIP, "face")).toBeNull();
    expect(nextTab("ArrowUp", STRIP, "face")).toBeNull();
    expect(nextTab("Enter", STRIP, "face")).toBeNull();
    expect(nextTab(" ", STRIP, "face")).toBeNull();
    expect(nextTab("a", STRIP, "face")).toBeNull();
  });

  it("answers no key on a strip with nothing on it", () => {
    expect(nextTab("ArrowRight", [], "face")).toBeNull();
    expect(nextTab("ArrowLeft", [], "face")).toBeNull();
    expect(nextTab("Home", [], "face")).toBeNull();
    expect(nextTab("End", [], "face")).toBeNull();
  });
});
