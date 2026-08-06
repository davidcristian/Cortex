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
    // And the map it was given is untouched, the reducer's state being handed around by reference.
    expect(draftOf(parkDraft(parked, "a", "rewritten"), "b")).toBe("second");
  });

  it("stores no entry for an empty field, in either direction", () => {
    // This is the whole of the eviction policy. A map keyed by chat that stored `""` would grow an
    // entry for every conversation the user ever opened and never lose one; keyed this way it holds
    // only chats with a sentence waiting in them, and emptying the field by hand ends that.
    expect(parkDraft({}, "a", "")).toEqual({});
    expect(parkDraft({ a: "half a question" }, "a", "")).toEqual({});
    expect("a" in parkDraft({ a: "x" }, "a", "")).toBe(false);
  });

  it("hands back the same map when nothing about it changed", () => {
    // A keystroke is not the only thing that asks: a re-measure at a new width re-parks the text
    // that is already there. Allocating a new map for it would be a new `drafts` identity per
    // resize, which is a new `state` for a fact that did not change.
    const held: Drafts = { a: "half a question" };
    expect(parkDraft(held, "a", "half a question")).toBe(held);
    expect(dropDraft(held, "b")).toBe(held);
    expect(dropDraft({}, "a")).toEqual({});
  });

  it("drops one chat's draft and keeps its neighbours', which is what a delete needs", () => {
    const held: Drafts = { a: "one", b: "two", c: "three" };
    expect(dropDraft(held, "b")).toEqual({ a: "one", c: "three" });
    // Not a mutation of the map the state was holding: the old state is still a valid past.
    expect(held).toEqual({ a: "one", b: "two", c: "three" });
  });
});
