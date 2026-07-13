import { describe, expect, it } from "vitest";

import type { SessionMessage, SessionSummary } from "../bridge/types";
import type { Action } from "./overlayState";
import { createInitialState, cycleTarget, initialState, isTurnActive, latestReply, reduce } from "./overlayState";

const summary = (sessionId: string): SessionSummary => ({
  sessionId,
  title: `title ${sessionId}`,
  preview: `preview ${sessionId}`,
  lastActivityUnixMs: 1000,
});

const run = (actions: Action[]) => actions.reduce(reduce, initialState);
const assistant = (s: ReturnType<typeof run>) => s.messages.find((m) => m.role === "assistant");
const submit = (text: string): Action => ({ kind: "submit", text });
const complete: Action = { kind: "event", event: { kind: "complete", turnId: "t-1" } };
const confirmRequest: Action = {
  kind: "event",
  event: {
    kind: "confirmRequest",
    confirmId: "c-1",
    toolName: "send_email",
    argumentsJson: '{"to":"ada@example.com"}',
    reason: "outbound",
  },
};

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
    expect(assistant(s)).toMatchObject({
      content: "Hello",
      tool: "read_email: reading",
      status: "swapping",
      statusState: "load",
    });
  });

  it("folds a thinking status's state so the chip can treat it distinctly", () => {
    let s = run([submit("q")]);
    s = reduce(s, {
      kind: "event",
      event: { kind: "status", state: "thinking", detail: "reasoning" },
    });
    expect(assistant(s)).toMatchObject({ status: "reasoning", statusState: "thinking" });
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

  it("stop ends the streaming turn in place, keeping the panel and the partial reply", () => {
    let s = run([{ kind: "open" }, submit("q")]);
    s = reduce(s, { kind: "event", event: { kind: "delta", text: "partial" } });
    const stopped = reduce(s, { kind: "stop" });
    expect(isTurnActive(stopped)).toBe(false);
    expect(stopped.mode).toBe("panel");
    expect(assistant(stopped)?.content).toBe("partial");
    expect(assistant(stopped)?.error).toBeNull();
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

  it("newChat mints a fresh session, clears the conversation, and closes the switcher", () => {
    const started = reduce(run([{ kind: "open" }, submit("q")]), { kind: "toggleSwitcher" });
    const fresh = reduce(started, { kind: "newChat", sessionId: "new-42" });
    expect(fresh.sessionId).toBe("new-42");
    expect(fresh.messages).toEqual([]);
    expect(fresh.title).toBe("New chat");
    expect(fresh.mode).toBe("panel");
    expect(fresh.switcherOpen).toBe(false);
  });

  it("sessionsLoaded stores the chat list and toggleSwitcher flips it open then shut", () => {
    const loaded = reduce(initialState, { kind: "sessionsLoaded", sessions: [summary("a")] });
    expect(loaded.sessions).toEqual([summary("a")]);
    const opened = reduce(loaded, { kind: "toggleSwitcher" });
    expect(opened.switcherOpen).toBe(true);
    expect(reduce(opened, { kind: "toggleSwitcher" }).switcherOpen).toBe(false);
  });

  it("toggleSheet flips the shortcut sheet open then shut, and dismiss closes it too", () => {
    const opened = reduce(reduce(initialState, { kind: "open" }), { kind: "toggleSheet" });
    expect(opened.sheetOpen).toBe(true);
    expect(reduce(opened, { kind: "toggleSheet" }).sheetOpen).toBe(false);
    // A dismissed panel never re-summons onto stale help.
    expect(reduce(opened, { kind: "dismiss" }).sheetOpen).toBe(false);
  });

  it("openSession hydrates a stored chat: messages, derived title, session id, closed switcher", () => {
    const messages: SessionMessage[] = [
      { role: "user", text: "about cats", turnId: "t", atUnixMs: 1 },
      { role: "assistant", text: "cats are great", turnId: "t", atUnixMs: 2 },
    ];
    const open = reduce({ ...initialState, switcherOpen: true }, {
      kind: "openSession",
      sessionId: "chat-7",
      messages,
    });
    expect(open.sessionId).toBe("chat-7");
    expect(open.title).toBe("about cats");
    expect(open.mode).toBe("panel");
    expect(open.switcherOpen).toBe(false);
    expect(open.seq).toBe(2);
    expect(open.messages.map((m) => [m.role, m.content, m.streaming])).toEqual([
      ["user", "about cats", false],
      ["assistant", "cats are great", false],
    ]);
  });

  it("openSession with no messages falls back to the New chat title", () => {
    const open = reduce(initialState, { kind: "openSession", sessionId: "empty", messages: [] });
    expect(open.title).toBe("New chat");
    expect(open.messages).toEqual([]);
  });

  it("adoptSession hydrates like openSession but keeps the overlay hidden", () => {
    const messages: SessionMessage[] = [
      { role: "user", text: "about cats", turnId: "t", atUnixMs: 1 },
      { role: "assistant", text: "cats are great", turnId: "t", atUnixMs: 2 },
    ];
    const adopted = reduce(initialState, { kind: "adoptSession", sessionId: "chat-7", messages });
    expect(adopted.mode).toBe("hidden");
    expect(adopted.sessionId).toBe("chat-7");
    expect(adopted.title).toBe("about cats");
    expect(adopted.seq).toBe(2);
    expect(adopted.messages.map((m) => [m.role, m.content, m.streaming])).toEqual([
      ["user", "about cats", false],
      ["assistant", "cats are great", false],
    ]);
  });

  it("adoptSession is a no-op once the overlay was summoned", () => {
    const summoned = reduce(initialState, { kind: "open" });
    const adopt: Action = {
      kind: "adoptSession",
      sessionId: "chat-7",
      messages: [{ role: "user", text: "hi", turnId: "t", atUnixMs: 1 }],
    };
    expect(reduce(summoned, adopt)).toBe(summoned);
  });

  it("adoptSession is a no-op once a turn was submitted", () => {
    // The racing submit already streamed into the fresh chat; adoption must not clobber it.
    const chatting = run([{ kind: "open" }, submit("q"), { kind: "dismiss" }]);
    const adopt: Action = { kind: "adoptSession", sessionId: "chat-7", messages: [] };
    expect(reduce(chatting, adopt)).toBe(chatting);
  });

  it("adoptSession is a no-op on an explicitly minted fresh chat that looks pristine", () => {
    // open → newChat → dismiss leaves {hidden, messages: [], seq: 0}: byte-identical to a
    // pristine boot on the seq/messages/mode proxy, yet the user explicitly chose a fresh
    // chat. The `touched` flag is what distinguishes them, so adoption must be a no-op here.
    const cleared = run([{ kind: "open" }, { kind: "newChat", sessionId: "n-2" }, { kind: "dismiss" }]);
    expect(cleared.mode).toBe("hidden");
    expect(cleared.messages).toEqual([]);
    expect(cleared.seq).toBe(0); // the proxy the old guard used cannot tell this from boot
    expect(cleared.sessionId).toBe("n-2");
    const adopt: Action = { kind: "adoptSession", sessionId: "chat-7", messages: [] };
    expect(reduce(cleared, adopt)).toBe(cleared);
    expect(cleared.sessionId).toBe("n-2"); // the user's fresh chat survives
  });

  it("confirmRequest raises the pending approval on a streaming turn", () => {
    const s = run([{ kind: "open" }, submit("send it"), confirmRequest]);
    expect(s.pendingConfirm).toEqual({
      confirmId: "c-1",
      toolName: "send_email",
      argumentsJson: '{"to":"ada@example.com"}',
      reason: "outbound",
    });
    expect(s.mode).toBe("panel");
  });

  it("confirmRequest on a dead turn is a no-op. A cancelled turn must not resurrect UI state", () => {
    expect(initialState.pendingConfirm).toBeNull();
    const stopped = run([{ kind: "open" }, submit("q"), { kind: "stop" }]);
    expect(reduce(stopped, confirmRequest)).toBe(stopped);
  });

  it("confirmRequest while minimized surfaces the preview, like a completed turn", () => {
    const s = run([{ kind: "open" }, submit("send it"), { kind: "dismiss" }, confirmRequest]);
    expect(s.mode).toBe("preview");
    expect(s.pendingConfirm?.confirmId).toBe("c-1");
  });

  it("confirmResolved clears the pending approval either way", () => {
    const pending = run([submit("send it"), confirmRequest]);
    expect(reduce(pending, { kind: "confirmResolved", approved: true }).pendingConfirm).toBeNull();
    expect(reduce(pending, { kind: "confirmResolved", approved: false }).pendingConfirm).toBeNull();
  });

  it("every turn-ending path drops the pending approval. The drop is the deny", () => {
    const pending = run([{ kind: "open" }, submit("send it"), confirmRequest]);
    const enders: Action[] = [
      complete,
      { kind: "event", event: { kind: "failed", code: "overloaded", message: "busy" } },
      { kind: "transportError", error: { kind: "connection", message: "down" } },
      { kind: "stop" },
      { kind: "dismiss" },
      { kind: "newChat", sessionId: "next" },
      { kind: "openSession", sessionId: "other", messages: [] },
    ];
    for (const ender of enders) {
      expect(reduce(pending, ender).pendingConfirm).toBeNull();
    }
  });

  it("previewFade waits out a pending approval AND a still-streaming turn", () => {
    const pending = run([{ kind: "open" }, submit("send it"), { kind: "dismiss" }, confirmRequest]);
    expect(pending.mode).toBe("preview");
    expect(reduce(pending, { kind: "previewFade" })).toBe(pending); // a question waits to be seen
    // The user answers, but the turn is still streaming. The preview must not fade from under it.
    const resolved = reduce(pending, { kind: "confirmResolved", approved: true });
    expect(reduce(resolved, { kind: "previewFade" })).toBe(resolved);
    // Only once the turn completes does the fade apply.
    const done = reduce(resolved, { kind: "event", event: { kind: "complete", turnId: "t" } });
    expect(reduce(done, { kind: "previewFade" }).mode).toBe("hidden");
  });

  it("latestReply returns the last assistant reply, or empty when there is none", () => {
    expect(latestReply(initialState)).toBe("");
    const s = reduce(run([submit("q")]), { kind: "event", event: { kind: "delta", text: "answer" } });
    expect(latestReply(s)).toBe("answer");
  });

  it("createInitialState seeds the session id", () => {
    expect(createInitialState("seed-1").sessionId).toBe("seed-1");
  });
});

describe("cycleTarget", () => {
  const sessions = [summary("newest"), summary("middle"), summary("oldest")];

  it("returns null when there are no sessions", () => {
    expect(cycleTarget([], "x", 1)).toBeNull();
    expect(cycleTarget([], "x", -1)).toBeNull();
  });

  it("steps newer (-1) and older (+1) within the list", () => {
    expect(cycleTarget(sessions, "middle", -1)).toBe("newest");
    expect(cycleTarget(sessions, "middle", 1)).toBe("oldest");
  });

  it("clamps at both ends (no wrap)", () => {
    expect(cycleTarget(sessions, "newest", -1)).toBeNull();
    expect(cycleTarget(sessions, "oldest", 1)).toBeNull();
  });

  it("an unsaved current chat enters the list only when going older", () => {
    expect(cycleTarget(sessions, "unsaved", 1)).toBe("newest");
    expect(cycleTarget(sessions, "unsaved", -1)).toBeNull();
  });
});
