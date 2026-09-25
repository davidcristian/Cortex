import { describe, expect, it } from "vitest";

import { type OverlayState, createInitialState, reduce } from "./overlayState";
import { refused, waitingOf } from "./pictureState";
import { NEW_CHAT_TITLE } from "./sessionState";
import type { ReadPicture } from "./pictures";

const read = (preview: string): ReadPicture => ({
  image: { data: new Uint8Array([1]), mimeType: "image/png", width: 4, height: 3 },
  preview,
});

const withTwo = (): OverlayState =>
  reduce(createInitialState("s1"), {
    kind: "attach",
    pictures: [read("data:a"), read("data:b")],
    problem: null,
  });

const previews = (state: OverlayState, sessionId = state.sessionId) =>
  waitingOf(state.pictures, sessionId).map((picture) => picture.preview);

describe("the composer's pictures", () => {
  it("gives each attached picture its own id and keeps them under the chat on screen", () => {
    const state = withTwo();
    const ids = waitingOf(state.pictures, "s1").map((picture) => picture.id);
    expect(new Set(ids).size).toBe(2);
    expect(previews(state)).toEqual(["data:a", "data:b"]);
    expect(waitingOf(state.pictures, "other")).toEqual([]);
    expect(state.touched).toBe(true);
  });

  it("shows the reader's problem, and the overflow note over it", () => {
    const problem = reduce(createInitialState("s1"), {
      kind: "attach",
      pictures: [],
      problem: "That picture could not be read.",
    });
    expect(problem.pictures.note).toBe("That picture could not be read.");
    const five = ["1", "2", "3", "4", "5"].map(read);
    const full = reduce(problem, { kind: "attach", pictures: five, problem: "unread" });
    expect(full.pictures.note).toBe("A message holds at most 4 pictures.");
    expect(previews(full)).toEqual(["1", "2", "3", "4"]);
  });

  it("removes one picture and the note with it, and forgets an emptied chat", () => {
    const state = { ...withTwo(), pictures: { ...withTwo().pictures, note: "old" } };
    const [first, second] = waitingOf(state.pictures, "s1");
    const one = reduce(state, { kind: "detach", id: first!.id });
    expect(previews(one)).toEqual(["data:b"]);
    expect(one.pictures.note).toBeNull();
    const none = reduce(one, { kind: "detach", id: second!.id });
    expect(none.pictures.waiting).toEqual({});
  });

  it("sends the pictures with the turn and empties the composer", () => {
    const sent = reduce(withTwo(), { kind: "submit", text: " look " });
    expect(waitingOf(sent.pictures, "s1")).toEqual([]);
    expect(sent.pictures.sent?.text).toBe("look");
    expect(sent.pictures.sent?.pictures.map((p) => p.preview)).toEqual(["data:a", "data:b"]);
  });

  it("hands a refused turn's text and pictures back with the brain's reason", () => {
    const sent = reduce(withTwo(), { kind: "submit", text: "look" });
    const failed = reduce(sent, {
      kind: "event",
      event: { kind: "failed", code: "attachment_refused", message: "attachment 2 is bad" },
    });
    expect(failed.drafts).toEqual({ s1: "look" });
    expect(previews(failed)).toEqual(["data:a", "data:b"]);
    expect(failed.pictures.note).toBe("attachment 2 is bad");
    expect(failed.pictures.sent).toBeNull();
    expect(failed.messages).toEqual([]);
    expect(failed.title).toBe(NEW_CHAT_TITLE);
    expect(failed.pictures.waiting).toEqual({ s1: sent.pictures.sent?.pictures });
  });

  it("keeps text typed during the turn, and adds pictures attached since after the sent ones", () => {
    const sent = reduce(withTwo(), { kind: "submit", text: "look" });
    const typed = reduce(sent, { kind: "draft", text: "newer" });
    const more = reduce(typed, { kind: "attach", pictures: [read("data:c")], problem: null });
    const failed = reduce(more, {
      kind: "event",
      event: { kind: "failed", code: "attachment_refused", message: "no" },
    });
    expect(failed.drafts).toEqual({ s1: "newer" });
    expect(previews(failed)).toEqual(["data:a", "data:b", "data:c"]);
  });

  it("drops the sent pictures when the turn ends any other way", () => {
    const sent = reduce(withTwo(), { kind: "submit", text: "look" });
    const failed = reduce(sent, {
      kind: "event",
      event: { kind: "failed", code: "inference_failed", message: "no" },
    });
    expect(failed.pictures.sent).toBeNull();
    expect(failed.pictures.note).toBeNull();
    expect(failed.messages.map((message) => message.role)).toEqual(["user", "assistant"]);
    expect(previews(failed)).toEqual([]);
    expect(failed.drafts).toEqual({});
  });

  it("keeps the earlier exchanges and the chat's title when a later turn is refused", () => {
    const first = reduce(createInitialState("s1"), { kind: "submit", text: "hello there" });
    const done = reduce(first, { kind: "event", event: { kind: "complete", turnId: "t1" } });
    const attached = reduce(done, { kind: "attach", pictures: [read("data:a")], problem: null });
    const sent = reduce(attached, { kind: "submit", text: "look" });
    const failed = reduce(sent, {
      kind: "event",
      event: { kind: "failed", code: "attachment_refused", message: "no" },
    });
    expect(failed.messages.map((message) => message.content)).toEqual(["hello there", ""]);
    expect(failed.title).toBe(done.title);
  });

  it("changes nothing when a refusal arrives with no turn to hand back", () => {
    const state = createInitialState("s1");
    expect(refused(state, null, "late")).toBe(state);
  });
});
