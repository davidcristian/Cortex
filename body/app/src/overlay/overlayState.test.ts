import { describe, expect, it } from "vitest";

import type { DueReminder, SessionMessage, SessionSummary } from "../bridge/types";
import type { Action, OverlayState } from "./overlayState";
import { createInitialState, cycleTarget, initialState, isTurnActive, latestReply, reduce } from "./overlayState";

const summary = (sessionId: string): SessionSummary => ({
  sessionId,
  title: `title ${sessionId}`,
  preview: `preview ${sessionId}`,
  lastActivityUnixMs: 1000,
  pinned: false,
});

const reminder = (reminderId: string): DueReminder => ({
  reminderId,
  text: `remember ${reminderId}`,
  firedAtUnixMs: 1000,
  recurring: false,
  tainted: false,
  sessionId: "s1",
});

const run = (actions: Action[]) => actions.reduce(reduce, initialState);
/**
 * Everything an event can change *about the turn*. An arriving event also proves the brain is
 * serving, so it legitimately refreshes the connection view (ADR-0011 addendum); the no-op
 * assertions below are about the turn, and compare this instead of whole-object identity.
 */
const turnOf = ({ link: _link, ...rest }: ReturnType<typeof run>) => rest;
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
    // A non-thinking status drives the chip only; it never joins the reasoning trace.
    expect(assistant(s)?.thoughts).toBe("");
  });

  it("folds a thinking status's state so the chip can treat it distinctly", () => {
    let s = run([submit("q")]);
    s = reduce(s, {
      kind: "event",
      event: { kind: "status", state: "thinking", detail: "reasoning" },
    });
    expect(assistant(s)).toMatchObject({ status: "reasoning", statusState: "thinking" });
  });

  it("accumulates every thinking status's detail into the collapsed thoughts trace", () => {
    let s = run([submit("q")]);
    s = reduce(s, { kind: "event", event: { kind: "status", state: "thinking", detail: "first" } });
    s = reduce(s, { kind: "event", event: { kind: "status", state: "thinking", detail: " second" } });
    // `status` holds only the latest delta; `thoughts` retains the whole scrubbed trace in order.
    expect(assistant(s)).toMatchObject({ status: " second", statusState: "thinking" });
    expect(assistant(s)?.thoughts).toBe("first second");
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

  it("openSession shows the switcher's authoritative title, not a locally re-derived one", () => {
    // The switcher row for this chat carries the brain's title (a user rename, a generated
    // title, or a longer brain-side truncation than the overlay's own); opening the chat must
    // show that same title so the header and the switcher row agree, rather than re-deriving
    // the header from the first message. Reddens if `openSession` re-derives from `messages`.
    const messages: SessionMessage[] = [
      { role: "user", text: "about cats", turnId: "t", atUnixMs: 1 },
      { role: "assistant", text: "cats are great", turnId: "t", atUnixMs: 2 },
    ];
    const listed = reduce(initialState, {
      kind: "sessionsLoaded",
      sessions: [
        { sessionId: "chat-7", title: "Everything about cats", preview: "p", lastActivityUnixMs: 2, pinned: false },
      ],
    });
    const open = reduce(listed, { kind: "openSession", sessionId: "chat-7", messages });
    expect(open.title).toBe("Everything about cats");
  });

  it("openSession falls back to the local derivation for a chat absent from the list", () => {
    // A reminder deep-link can open a chat outside the loaded recency window: no summary is in
    // hand, so the first-message derivation stands (the recorded residual of this fix, whose
    // disagreement the switcher cannot show anyway, having no row for the out-of-window chat).
    const messages: SessionMessage[] = [
      { role: "user", text: "about dogs", turnId: "t", atUnixMs: 1 },
    ];
    const listed = reduce(initialState, {
      kind: "sessionsLoaded",
      sessions: [
        { sessionId: "elsewhere", title: "unrelated chat", preview: "p", lastActivityUnixMs: 2, pinned: false },
      ],
    });
    const open = reduce(listed, { kind: "openSession", sessionId: "chat-9", messages });
    expect(open.title).toBe("about dogs");
  });

  it("sessionDeleted drops another chat's row without disturbing the open chat", () => {
    // Deleting a chat that is not the current one only removes it from the switcher list; the
    // panel, its session id, and its messages are untouched (the deleted chat was never on screen).
    const started = run([{ kind: "open" }, submit("my question")]);
    const listed = reduce(started, {
      kind: "sessionsLoaded",
      sessions: [summary(started.sessionId), summary("other")],
    });
    const after = reduce(listed, {
      kind: "sessionDeleted",
      sessionId: "other",
      fallbackSessionId: "unused-fresh-id",
    });
    expect(after.sessions.map((s) => s.sessionId)).toEqual([started.sessionId]); // "other" gone
    expect(after.sessionId).toBe(started.sessionId); // the open chat's identity is unchanged
    expect(after.messages).toBe(started.messages); // its transcript is untouched
    expect(after.touched).toBe(true);
  });

  it("sessionDeleted on the CURRENT chat falls back to a fresh empty chat, never a deleted one", () => {
    // The current-session hazard: deleting the open chat must not leave its transcript on screen.
    // The panel resets to a fresh empty chat under the minted fallback id (a new-chat in place),
    // and the deleted row leaves the list. The panel stays open so the user keeps their place.
    const started = run([{ kind: "open" }, submit("secret question")]);
    const listed = reduce(started, {
      kind: "sessionsLoaded",
      sessions: [summary(started.sessionId), summary("keep")],
    });
    const after = reduce(listed, {
      kind: "sessionDeleted",
      sessionId: started.sessionId,
      fallbackSessionId: "fresh-99",
    });
    expect(after.sessionId).toBe("fresh-99"); // a brand-new chat, not the deleted one
    expect(after.title).toBe("New chat");
    expect(after.messages).toEqual([]); // the deleted transcript is gone from the panel
    expect(after.seq).toBe(0);
    expect(after.mode).toBe("panel"); // the panel stays open
    expect(after.sessions.map((s) => s.sessionId)).toEqual(["keep"]); // deleted row removed
    expect(after.touched).toBe(true);
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

  it("adoptSession shows the most recent chat's switcher title, not a re-derived one", () => {
    // Cold-start adoption targets `sessions[0]`, always in the loaded list, so it too carries
    // the authoritative title: summoning lands on a header that matches the switcher's top row.
    const messages: SessionMessage[] = [
      { role: "user", text: "about cats", turnId: "t", atUnixMs: 1 },
    ];
    const listed = reduce(initialState, {
      kind: "sessionsLoaded",
      sessions: [
        { sessionId: "chat-7", title: "Everything about cats", preview: "p", lastActivityUnixMs: 2, pinned: false },
      ],
    });
    const adopted = reduce(listed, { kind: "adoptSession", sessionId: "chat-7", messages });
    expect(adopted.title).toBe("Everything about cats");
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
    const after = reduce(stopped, confirmRequest);
    expect(turnOf(after)).toEqual(turnOf(stopped));
    // Identity on the collections too: nothing was rebuilt, so nothing could have been revived.
    expect(after.messages).toBe(stopped.messages);
    expect(after.pendingConfirm).toBeNull();
  });

  it("confirmRequest while minimized surfaces the preview, like a completed turn", () => {
    const s = run([{ kind: "open" }, submit("send it"), { kind: "dismiss" }, confirmRequest]);
    expect(s.mode).toBe("preview");
    expect(s.pendingConfirm?.confirmId).toBe("c-1");
  });

  it("confirmResolved closes the card the brain stopped waiting on", () => {
    // The timeout case (ADR-0022): the brain denied on the user's behalf, so the question
    // must leave before the user can click Approve on an answer that already happened.
    const pending = run([{ kind: "open" }, submit("send it"), confirmRequest]);
    const resolved = reduce(pending, {
      kind: "event",
      event: { kind: "confirmResolved", confirmId: "c-1", outcome: "timeout" },
    });
    expect(resolved.pendingConfirm).toBeNull();
    // Non-terminal: the turn keeps streaming its declined reply behind the closed card.
    expect(isTurnActive(resolved)).toBe(true);
  });

  it("confirmResolved for another id leaves the card alone", () => {
    // A late resolution for a question already answered and replaced, or one this overlay
    // never showed: the same stale-id rule the answer path has.
    const pending = run([{ kind: "open" }, submit("send it"), confirmRequest]);
    const other: Action = {
      kind: "event",
      event: { kind: "confirmResolved", confirmId: "c-other", outcome: "timeout" },
    };
    expect(turnOf(reduce(pending, other))).toEqual(turnOf(pending));
    expect(reduce(pending, other).pendingConfirm).toBe(pending.pendingConfirm);
    const nothingPending = run([{ kind: "open" }, submit("send it")]);
    expect(turnOf(reduce(nothingPending, other))).toEqual(turnOf(nothingPending));
  });

  it("confirmAnswered clears the pending approval either way", () => {
    const pending = run([submit("send it"), confirmRequest]);
    expect(reduce(pending, { kind: "confirmAnswered", approved: true }).pendingConfirm).toBeNull();
    expect(reduce(pending, { kind: "confirmAnswered", approved: false }).pendingConfirm).toBeNull();
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
    const resolved = reduce(pending, { kind: "confirmAnswered", approved: true });
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

  it("remindersLoaded replaces the list wholesale, so anything acked elsewhere leaves", () => {
    const first = reduce(initialState, {
      kind: "remindersLoaded",
      reminders: [reminder("r-1"), reminder("r-2")],
    });
    expect(first.reminders.map((r) => r.reminderId)).toEqual(["r-1", "r-2"]);
    const second = reduce(first, { kind: "remindersLoaded", reminders: [reminder("r-3")] });
    expect(second.reminders.map((r) => r.reminderId)).toEqual(["r-3"]);
  });

  it("reminderDismissed drops just that card, and an unknown id is a no-op", () => {
    const loaded = reduce(initialState, {
      kind: "remindersLoaded",
      reminders: [reminder("r-1"), reminder("r-2")],
    });
    const dismissed = reduce(loaded, { kind: "reminderDismissed", reminderId: "r-1" });
    expect(dismissed.reminders.map((r) => r.reminderId)).toEqual(["r-2"]);
    // A double-click or a stale card re-fires the same action; the list must not change.
    const again = reduce(dismissed, { kind: "reminderDismissed", reminderId: "r-1" });
    expect(again.reminders.map((r) => r.reminderId)).toEqual(["r-2"]);
  });

  it("reminders survive the turn and chat actions that clear other surfaces", () => {
    const loaded = reduce(initialState, { kind: "remindersLoaded", reminders: [reminder("r-1")] });
    // Delivery is not conversation: a new chat empties messages but keeps what is undelivered.
    const fresh = reduce(loaded, { kind: "newChat", sessionId: "s2" });
    expect(fresh.messages).toEqual([]);
    expect(fresh.reminders.map((r) => r.reminderId)).toEqual(["r-1"]);
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

describe("the screen-capture indicator", () => {
  const streaming = (): OverlayState =>
    reduce(reduce(createInitialState("s1"), { kind: "open" }), {
      kind: "submit",
      text: "what is on my screen?",
    });

  it("lights when the assistant looks at the screen", () => {
    const before = streaming();
    expect(before.capturing).toBe(false);
    const after = reduce(before, {
      kind: "event",
      event: { kind: "toolActivity", toolName: "capture_screen", summary: "primary display" },
    });
    expect(after.capturing).toBe(true);
  });

  it("stays lit for the rest of the turn, past later tool activity", () => {
    // The fact the user is owed is "the assistant looked at my screen during this reply", not
    // "a tool ran for a moment", so a later chip must not put the indicator out.
    const looked = reduce(streaming(), {
      kind: "event",
      event: { kind: "toolActivity", toolName: "capture_screen", summary: "primary display" },
    });
    const later = reduce(looked, {
      kind: "event",
      event: { kind: "toolActivity", toolName: "get_volume", summary: "reading" },
    });
    expect(later.capturing).toBe(true);
    expect(later.messages.at(-1)?.tool).toBe("get_volume: reading");
  });

  it("stays dark for a turn that only ran other tools", () => {
    const after = reduce(streaming(), {
      kind: "event",
      event: { kind: "toolActivity", toolName: "get_volume", summary: "reading" },
    });
    expect(after.capturing).toBe(false);
  });

  it("goes out when the turn completes", () => {
    const looked = reduce(streaming(), {
      kind: "event",
      event: { kind: "toolActivity", toolName: "capture_screen", summary: "primary display" },
    });
    const done = reduce(looked, { kind: "event", event: { kind: "complete", turnId: "t1" } });
    expect(done.capturing).toBe(false);
  });

  it("goes out when the turn fails", () => {
    const looked = reduce(streaming(), {
      kind: "event",
      event: { kind: "toolActivity", toolName: "capture_screen", summary: "primary display" },
    });
    const dead = reduce(looked, {
      kind: "event",
      event: { kind: "failed", code: "INTERNAL", message: "boom" },
    });
    expect(dead.capturing).toBe(false);
  });
});
