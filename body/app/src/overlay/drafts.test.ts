import { describe, expect, it } from "vitest";

import { type Drafts, draftOf, dropDraft, parkDraft } from "./drafts";

describe("drafts", () => {
  it("shows an empty field for a chat nobody has typed into", () => {
    expect(draftOf({}, "a")).toBe("");
    expect(draftOf({ b: "half a question" }, "a")).toBe("");
    expect(draftOf({ a: "half a question" }, "a")).toBe("half a question");
  });

  it("parks text under one chat and leaves every other chat alone", () => {
    const parked = parkDraft({ a: "first" }, "b", "second");
    expect(parked).toEqual({ a: "first", b: "second" });
    expect(draftOf(parkDraft(parked, "a", "rewritten"), "b")).toBe("second");
  });

  it("stores no entry for an empty field, in either direction", () => {
    expect(parkDraft({}, "a", "")).toEqual({});
    expect(parkDraft({ a: "half a question" }, "a", "")).toEqual({});
    expect("a" in parkDraft({ a: "x" }, "a", "")).toBe(false);
  });

  it("hands back the same map when nothing about it changed", () => {
    const held: Drafts = { a: "half a question" };
    expect(parkDraft(held, "a", "half a question")).toBe(held);
    expect(dropDraft(held, "b")).toBe(held);
    expect(dropDraft({}, "a")).toEqual({});
  });

  it("drops one chat's draft and keeps its neighbours', which is what a delete needs", () => {
    const held: Drafts = { a: "one", b: "two", c: "three" };
    expect(dropDraft(held, "b")).toEqual({ a: "one", c: "three" });
    expect(held).toEqual({ a: "one", b: "two", c: "three" });
  });
});
