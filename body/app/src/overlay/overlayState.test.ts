import { describe, expect, it } from "vitest";

import type { Action } from "./overlayState";
import { initialState, isTurnActive, latestReply, reduce } from "./overlayState";

const run = (actions: Action[]) => actions.reduce(reduce, initialState);
const assistant = (s: ReturnType<typeof run>) => s.messages.find((m) => m.role === "assistant");
const submit = (text: string): Action => ({ kind: "submit", text });
const complete: Action = { kind: "event", event: { kind: "complete", turnId: "t-1" } };

describe("overlayState reducer", () => {
  it("open shows the panel", () => {
    expect(reduce(initialState, { kind: "open" }).mode).toBe("panel");
  });

  it("submit adds a user message and a streaming assistant message, and titles the chat", () => {
    const s = run([{ kind: "open" }, submit("Hello there")]);
    expect(s.messages.map((m) => [m.role, m.streaming])).toEqual([
      ["user", false],
      ["assistant", true],
    ]);
    expect(s.messages[0]).toMatchObject({ content: "Hello there" });
    expect(s.title).toBe("Hello there");
    expect(s.seq).toBe(2);
    expect(isTurnActive(s)).toBe(true);
  });

  it("submit ignores empty input and mid-stream input (returns state unchanged)", () => {
    const panel = reduce(initialState, { kind: "open" });
    expect(reduce(panel, submit("   "))).toBe(panel);
    const streaming = run([{ kind: "open" }, submit("one")]);
    expect(reduce(streaming, submit("two"))).toBe(streaming);
  });

  it("keeps an existing title on later turns and truncates/normalizes new ones", () => {
    const first = reduce(run([submit("first question")]), complete);
    expect(reduce(first, submit("second")).title).toBe("first question");
    expect(run([submit("a".repeat(50))]).title).toBe(`${"a".repeat(32)}…`);
    expect(run([submit("hello    world")]).title).toBe("hello world");
  });

  it("folds delta, tool activity, and status into the streaming message", () => {
    let s = run([submit("q")]);
    s = reduce(s, { kind: "event", event: { kind: "delta", text: "Hel" } });
    s = reduce(s, { kind: "event", event: { kind: "delta", text: "lo" } });
    s = reduce(s, {
      kind: "event",
      event: { kind: "toolActivity", toolName: "read_email", summary: "reading" },
    });
    s = reduce(s, { kind: "event", event: { kind: "status", state: "load", detail: "swapping" } });
    expect(assistant(s)).toMatchObject({ content: "Hello", tool: "read_email: reading", status: "swapping" });
  });

  it("complete ends the turn and stays in the panel", () => {
    const s = reduce(run([{ kind: "open" }, submit("q")]), complete);
    expect(isTurnActive(s)).toBe(false);
    expect(s.mode).toBe("panel");
    expect(assistant(s)?.streaming).toBe(false);
  });

  it("failed and transportError end the turn with an error message", () => {
    const failed = reduce(run([submit("q")]), {
      kind: "event",
      event: { kind: "failed", code: "overloaded", message: "busy" },
    });
    expect(assistant(failed)?.error).toBe("overloaded: busy");
    const errored = reduce(run([submit("q")]), {
      kind: "transportError",
      error: { kind: "connection", message: "cannot reach the brain" },
    });
    expect(assistant(errored)?.error).toBe("cannot reach the brain");
    expect(isTurnActive(errored)).toBe(false);
  });

  it("dismiss minimizes to the orb mid-stream, else hides", () => {
    const streaming = run([{ kind: "open" }, submit("q")]);
    expect(reduce(streaming, { kind: "dismiss" }).mode).toBe("orb");
    const done = reduce(streaming, complete);
    expect(reduce(done, { kind: "dismiss" }).mode).toBe("hidden");
  });

  it("completing while minimized surfaces the preview (the signature flow)", () => {
    const orb = reduce(run([{ kind: "open" }, submit("q")]), { kind: "dismiss" });
    expect(orb.mode).toBe("orb");
    const preview = reduce(orb, complete);
    expect(preview.mode).toBe("preview");
    expect(isTurnActive(preview)).toBe(false);
  });

  it("previewFade hides only from the preview", () => {
    const preview = reduce(reduce(run([{ kind: "open" }, submit("q")]), { kind: "dismiss" }), complete);
    expect(reduce(preview, { kind: "previewFade" }).mode).toBe("hidden");
    const panel = reduce(initialState, { kind: "open" });
    expect(reduce(panel, { kind: "previewFade" })).toBe(panel);
  });

  it("newChat clears the conversation back to a fresh panel", () => {
    const fresh = reduce(run([{ kind: "open" }, submit("q")]), { kind: "newChat" });
    expect(fresh.messages).toEqual([]);
    expect(fresh.title).toBe("New chat");
    expect(fresh.mode).toBe("panel");
  });

  it("latestReply returns the last assistant reply, or empty when there is none", () => {
    expect(latestReply(initialState)).toBe("");
    const s = reduce(run([submit("q")]), { kind: "event", event: { kind: "delta", text: "answer" } });
    expect(latestReply(s)).toBe("answer");
  });
});
