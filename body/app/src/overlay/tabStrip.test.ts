import { describe, expect, it } from "vitest";

import { nextTab } from "./tabStrip";

const STRIP = ["face", "chords", "voice"] as const;

describe("nextTab", () => {
  it("walks right along the strip and wraps off the end", () => {
    expect(nextTab("ArrowRight", STRIP, "face")).toBe("chords");
    expect(nextTab("ArrowRight", STRIP, "chords")).toBe("voice");
    // The wrap is the decision: on a strip of two, stopping here would make Right a no-op half the
    // time, which reads as a broken key rather than as a strip with an end.
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
    // End on the last tab is the last tab: these two are absolute, so there is nothing to wrap
    // around, and a wrapping End would be a key that leaves the end it was pressed to reach.
    expect(nextTab("End", STRIP, "voice")).toBe("voice");
    expect(nextTab("Home", STRIP, "face")).toBe("face");
  });

  it("leaves every other key alone, the vertical arrows included", () => {
    // Ctrl and these two cycle chats overlay-wide. A horizontal strip that also answered them
    // would put two meanings on one gesture, told apart only by a modifier.
    expect(nextTab("ArrowDown", STRIP, "face")).toBeNull();
    expect(nextTab("ArrowUp", STRIP, "face")).toBeNull();
    expect(nextTab("Enter", STRIP, "face")).toBeNull();
    expect(nextTab(" ", STRIP, "face")).toBeNull();
    expect(nextTab("a", STRIP, "face")).toBeNull();
  });

  it("answers no key on a strip with nothing on it", () => {
    // The one edge in the arithmetic: `indexOf` reports -1 and every branch below stays total, so
    // the lookup finds nothing and the caller is told so rather than handed an undefined tab.
    expect(nextTab("ArrowRight", [], "face")).toBeNull();
    expect(nextTab("ArrowLeft", [], "face")).toBeNull();
    expect(nextTab("Home", [], "face")).toBeNull();
    expect(nextTab("End", [], "face")).toBeNull();
  });
});
