import { describe, expect, it } from "vitest";

import type { DueReminder, SessionMessage, SessionSummary, TurnEvent } from "../bridge/types";
import { NO_OTHER_CHATS } from "./notice";
import type { Action, OverlayState } from "./overlayState";
import { createInitialState, cycleTarget, draftOf, initialState, isTurnActive, latestReply, reduce } from "./overlayState";

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
/** Everything an event can change *about the turn*. */
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
    expect(run([submit("a".repeat(50))]).title).toBe(`${"a".repeat(48)}…`);
    expect(run([submit("hello    world")]).title).toBe("hello world");
  });

  it("titles a fresh chat exactly as the brain will title it once the chat is listed", () => {
    const opening = "How does the session title truncation work";
    const listed: SessionSummary = {
      sessionId: "chat-9",
      title: opening,
      preview: "p",
      lastActivityUnixMs: 3,
      pinned: false,
    };
    const submitted = run([{ kind: "newChat", sessionId: "chat-9", announce: false }, submit(opening)]);
    expect(submitted.title).toBe(listed.title);
    const refreshed = reduce(submitted, { kind: "sessionsLoaded", sessions: [listed] });
    const reopened = reduce(refreshed, {
      kind: "openSession",
      sessionId: "chat-9",
      messages: [{ role: "user", text: opening, turnId: "t", atUnixMs: 1 }],
      announce: false,
    });
    expect(reopened.title).toBe(listed.title);
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
    const started = reduce(run([{ kind: "open" }, submit("q")]), {
      kind: "toggleSwitcher",
      announce: false,
    });
    const fresh = reduce(started, { kind: "newChat", sessionId: "new-42", announce: false });
    expect(fresh.sessionId).toBe("new-42");
    expect(fresh.messages).toEqual([]);
    expect(fresh.title).toBe("New chat");
    expect(fresh.mode).toBe("panel");
    expect(fresh.switcherOpen).toBe(false);
  });

  it("a chat arriving takes the console off the panel, from either tab and by either gesture", () => {
    for (const tab of ["appearance", "shortcuts"] as const) {
      const reading = reduce(run([{ kind: "open" }, submit("q")]), { kind: "openConsole", tab });
      expect(reading.consoleTab).toBe(tab);

      const fresh = reduce(reading, { kind: "newChat", sessionId: "new-42", announce: false });
      expect(fresh.consoleTab).toBeNull();
      expect(fresh.messages).toEqual([]);
      expect(fresh.mode).toBe("panel");

      const cycled = reduce(reading, { kind: "openSession", sessionId: "chat-7", messages: [], announce: false });
      expect(cycled.consoleTab).toBeNull();
      expect(cycled.sessionId).toBe("chat-7");
      expect(cycled.mode).toBe("panel");
    }
  });

  it("a delete and a cold-start adoption both leave the console where it was", () => {
    const reading = reduce(run([{ kind: "open" }, submit("q")]), {
      kind: "openConsole",
      tab: "appearance",
    });
    const listed = reduce(reading, {
      kind: "sessionsLoaded",
      sessions: [summary(reading.sessionId)],
    });
    const deleted = reduce(listed, {
      kind: "sessionDeleted",
      sessionId: listed.sessionId,
      fallbackSessionId: "fresh-1",
    });
    expect(deleted.consoleTab).toBe("appearance");
    expect(deleted.sessionId).toBe("fresh-1");
    const adopt: Action = { kind: "adoptSession", sessionId: "chat-7", messages: [] };
    expect(reduce(listed, adopt)).toBe(listed);
  });

  it("sessionsLoaded stores the chat list and toggleSwitcher flips it open then shut", () => {
    const loaded = reduce(initialState, { kind: "sessionsLoaded", sessions: [summary("a")] });
    expect(loaded.sessions).toEqual([summary("a")]);
    const opened = reduce(loaded, { kind: "toggleSwitcher", announce: false });
    expect(opened.switcherOpen).toBe(true);
    expect(reduce(opened, { kind: "toggleSwitcher", announce: false }).switcherOpen).toBe(false);
  });

  it("says what an opened list holds, when the key opened it and the chat is on screen", () => {
    const listed = run([
      { kind: "open" },
      { kind: "sessionsLoaded", sessions: [summary("a"), summary("b")] },
    ]);
    const opened = reduce(listed, { kind: "toggleSwitcher", announce: true });
    expect(opened.notice?.text).toBe("Recent chats open. 2 chats.");
    expect(reduce({ ...listed, sessions: [] }, { kind: "toggleSwitcher", announce: true }).notice?.text)
      .toBe(`Recent chats open. ${NO_OTHER_CHATS}.`);
  });

  it("stays silent for the gesture that carries the state under the reader's own caret", () => {
    const listed = run([{ kind: "open" }, { kind: "sessionsLoaded", sessions: [summary("a")] }]);
    expect(reduce(listed, { kind: "toggleSwitcher", announce: false }).notice).toBeNull();
  });

  it("says nothing about a list closing, whichever gesture closed it", () => {
    const open = run([
      { kind: "open" },
      { kind: "sessionsLoaded", sessions: [summary("a")] },
      { kind: "toggleSwitcher", announce: false },
    ]);
    expect(open.switcherOpen).toBe(true);
    const shut = reduce(open, { kind: "toggleSwitcher", announce: true });
    expect(shut.switcherOpen).toBe(false);
    expect(shut.notice).toBeNull();
  });

  it("Ctrl+K from a tucked panel brings the panel back with the list on it", () => {
    const sessions = [summary("a")];
    const tucked: OverlayState = { ...initialState, sessions };
    const opened = reduce(tucked, { kind: "toggleSwitcher", announce: true });
    expect(opened.mode).toBe("panel");
    expect(opened.touched).toBe(true);
    expect(opened.switcherOpen).toBe(true);
    expect(opened.notice?.text).toBe("Recent chats open. 1 chat.");
  });

  it("Ctrl+K from behind the console takes the console off and shows the list", () => {
    const sessions = [summary("a")];
    const behindConsole = run([
      { kind: "open" },
      { kind: "sessionsLoaded", sessions },
      { kind: "toggleConsole", tab: "shortcuts" },
    ]);
    const opened = reduce(behindConsole, { kind: "toggleSwitcher", announce: true });
    expect(opened.consoleTab).toBeNull();
    expect(opened.switcherOpen).toBe(true);
    expect(opened.notice?.text).toBe("Recent chats open. 1 chat.");
  });

  it("a press off the chat opens rather than toggling, so a summon cannot shut an unseen list", () => {
    const sessions = [summary("a")];
    const open = run([
      { kind: "open" },
      { kind: "sessionsLoaded", sessions },
      { kind: "toggleSwitcher", announce: false },
    ]);
    expect(open.switcherOpen).toBe(true);
    const tuckedWithList = reduce(open, { kind: "dismiss" });
    expect(reduce(tuckedWithList, { kind: "toggleSwitcher", announce: false }).switcherOpen).toBe(
      true,
    );
    expect(reduce(open, { kind: "toggleSwitcher", announce: false }).switcherOpen).toBe(false);
  });

  it("carries a standing sentence through a silent toggle rather than clearing it", () => {
    const spoken = run([
      { kind: "open" },
      { kind: "sessionsLoaded", sessions: [summary("a")] },
      { kind: "newChat", sessionId: "n-1", announce: true },
    ]);
    expect(spoken.notice?.text).toBe("Switched to New chat.");
    expect(reduce(spoken, { kind: "toggleSwitcher", announce: false }).notice).toBe(spoken.notice);
  });

  it("toggleConsole opens its own tab, closes it again, and switches from the other one", () => {
    const panel = reduce(initialState, { kind: "open" });
    const appearance = reduce(panel, { kind: "toggleConsole", tab: "appearance" });
    expect(appearance.consoleTab).toBe("appearance");
    expect(reduce(appearance, { kind: "toggleConsole", tab: "appearance" }).consoleTab).toBeNull();
    expect(reduce(appearance, { kind: "toggleConsole", tab: "shortcuts" }).consoleTab).toBe(
      "shortcuts",
    );
  });

  it("? from a tucked panel puts the shortcuts on screen instead of behind a hidden window", () => {
    const tuckedWithTab = reduce(reduce(initialState, { kind: "toggleConsole", tab: "shortcuts" }), {
      kind: "dismiss",
    });
    expect(tuckedWithTab.mode).toBe("hidden");
    const shown = reduce(tuckedWithTab, { kind: "toggleConsole", tab: "shortcuts" });
    expect(shown.mode).toBe("panel");
    expect(shown.touched).toBe(true);
    expect(shown.consoleTab).toBe("shortcuts");
  });

  it("openConsole shows a tab and is idempotent, so the tab strip cannot close the console", () => {
    const shortcuts = reduce(initialState, { kind: "openConsole", tab: "shortcuts" });
    expect(shortcuts.consoleTab).toBe("shortcuts");
    expect(reduce(shortcuts, { kind: "openConsole", tab: "shortcuts" }).consoleTab).toBe(
      "shortcuts",
    );
    expect(reduce(shortcuts, { kind: "openConsole", tab: "appearance" }).consoleTab).toBe(
      "appearance",
    );
  });

  it("closeConsole leaves in one step, and a dismissed panel keeps the console until it returns", () => {
    for (const tab of ["appearance", "shortcuts"] as const) {
      const opened = reduce(reduce(initialState, { kind: "open" }), { kind: "openConsole", tab });
      expect(reduce(opened, { kind: "closeConsole" }).consoleTab).toBeNull();
      const gone = reduce(opened, { kind: "dismiss" });
      expect(gone.consoleTab).toBe(tab);
      expect(gone.mode).toBe("hidden");
      expect(reduce(gone, { kind: "open" }).consoleTab).toBeNull();
    }
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
      announce: false,
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
    const open = reduce(initialState, { kind: "openSession", sessionId: "empty", messages: [], announce: false });
    expect(open.title).toBe("New chat");
    expect(open.messages).toEqual([]);
  });

  it("openSession shows the switcher's authoritative title, not a locally re-derived one", () => {
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
    const open = reduce(listed, { kind: "openSession", sessionId: "chat-7", messages, announce: false });
    expect(open.title).toBe("Everything about cats");
  });

  it("openSession falls back to the local derivation for a chat absent from the list", () => {
    const messages: SessionMessage[] = [
      { role: "user", text: "about dogs", turnId: "t", atUnixMs: 1 },
    ];
    const listed = reduce(initialState, {
      kind: "sessionsLoaded",
      sessions: [
        { sessionId: "elsewhere", title: "unrelated chat", preview: "p", lastActivityUnixMs: 2, pinned: false },
      ],
    });
    const open = reduce(listed, { kind: "openSession", sessionId: "chat-9", messages, announce: false });
    expect(open.title).toBe("about dogs");
  });

  it("sessionDeleted drops another chat's row without disturbing the open chat", () => {
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
    expect(after.sessions.map((s) => s.sessionId)).toEqual([started.sessionId]);
    expect(after.sessionId).toBe(started.sessionId);
    expect(after.messages).toBe(started.messages);
    expect(after.touched).toBe(true);
  });

  it("sessionDeleted on the CURRENT chat falls back to a fresh empty chat, never a deleted one", () => {
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
    expect(after.sessionId).toBe("fresh-99");
    expect(after.title).toBe("New chat");
    expect(after.messages).toEqual([]);
    expect(after.seq).toBe(0);
    expect(after.mode).toBe("panel");
    expect(after.sessions.map((s) => s.sessionId)).toEqual(["keep"]);
    expect(after.touched).toBe(true);
  });

  it("openSession says which chat arrived, unless the gesture that opened it already named one", () => {
    const listed = reduce(initialState, {
      kind: "sessionsLoaded",
      sessions: [
        { sessionId: "chat-7", title: "Everything about cats", preview: "p", lastActivityUnixMs: 2, pinned: false },
      ],
    });
    const cycled = reduce(listed, {
      kind: "openSession",
      sessionId: "chat-7",
      messages: [],
      announce: true,
    });
    expect(cycled.notice).toEqual({ text: "Switched to Everything about cats.", count: 1 });
    expect(cycled.notice?.text).toContain(cycled.title);
    const picked = reduce(cycled, {
      kind: "openSession",
      sessionId: "chat-7",
      messages: [],
      announce: false,
    });
    expect(picked.notice).toBeNull();
  });

  it("counts each announcement, so two chats under one title are two things said", () => {
    const first = reduce(initialState, { kind: "newChat", sessionId: "a", announce: true });
    const second = reduce(first, { kind: "newChat", sessionId: "b", announce: true });
    expect(first.notice).toEqual({ text: "Switched to New chat.", count: 1 });
    expect(second.notice).toEqual({ text: "Switched to New chat.", count: 2 });
    expect(reduce(second, { kind: "newChat", sessionId: "c", announce: false }).notice).toBeNull();
  });

  it("a row leaving the switcher says so, and says what the list holds now", () => {
    const started = run([{ kind: "open" }, submit("secret question")]);
    const listed = reduce(started, {
      kind: "sessionsLoaded",
      sessions: [summary(started.sessionId), summary("keep"), summary("also")],
    });
    const other = reduce(listed, {
      kind: "sessionDeleted",
      sessionId: "keep",
      fallbackSessionId: "unused",
    });
    expect(other.notice).toEqual({ text: "Chat deleted. 2 chats left.", count: 1 });
    const down = reduce(other, {
      kind: "sessionDeleted",
      sessionId: "also",
      fallbackSessionId: "unused",
    });
    expect(down.notice).toEqual({ text: "Chat deleted. 1 chat left.", count: 2 });
    const empty = reduce(down, {
      kind: "sessionDeleted",
      sessionId: started.sessionId,
      fallbackSessionId: "fresh-1",
    });
    expect(empty.notice?.text).toContain(NO_OTHER_CHATS);
  });

  it("a delete that also swaps the chat says both, in one sentence and in order", () => {
    const started = run([{ kind: "open" }, submit("secret question")]);
    const listed = reduce(started, {
      kind: "sessionsLoaded",
      sessions: [summary(started.sessionId), summary("keep")],
    });
    const current = reduce(listed, {
      kind: "sessionDeleted",
      sessionId: started.sessionId,
      fallbackSessionId: "fresh-99",
    });
    expect(current.notice).toEqual({
      text: "Chat deleted. 1 chat left. Switched to New chat.",
      count: 1,
    });
  });

  it("says nothing for a delete that removed no row, on either path", () => {
    const listed = reduce(initialState, {
      kind: "sessionsLoaded",
      sessions: [summary("keep")],
    });
    const spoke = reduce(listed, {
      kind: "sessionDeleted",
      sessionId: "keep",
      fallbackSessionId: "unused",
    });
    const again = reduce(spoke, {
      kind: "sessionDeleted",
      sessionId: "keep",
      fallbackSessionId: "unused",
    });
    expect(again.notice).toBe(spoke.notice);
    const open = reduce(again, {
      kind: "sessionDeleted",
      sessionId: again.sessionId,
      fallbackSessionId: "fresh-2",
    });
    expect(open.notice).toEqual({ text: "Switched to New chat.", count: 2 });
  });

  it("counts every gesture that replaces the conversation, and nothing else, as an arrival", () => {
    const listed = reduce(initialState, { kind: "sessionsLoaded", sessions: [summary("chat-7")] });
    expect(listed.arrival).toBe(0);
    const row = reduce(listed, { kind: "openSession", sessionId: "chat-7", messages: [], announce: false });
    const key = reduce(row, { kind: "openSession", sessionId: "chat-7", messages: [], announce: true });
    expect([row.arrival, key.arrival]).toEqual([1, 2]);
    expect(reduce(key, { kind: "openSession", sessionId: "chat-7", messages: [], announce: false }).arrival).toBe(3);
    const pencil = reduce(key, { kind: "newChat", sessionId: "n-1", announce: false });
    const ctrlN = reduce(pencil, { kind: "newChat", sessionId: "n-2", announce: true });
    expect([pencil.arrival, ctrlN.arrival]).toEqual([3, 4]);
    const open = reduce(listed, { kind: "openSession", sessionId: "chat-7", messages: [], announce: false });
    expect(reduce(open, { kind: "sessionDeleted", sessionId: "chat-7", fallbackSessionId: "f" }).arrival).toBe(2);
    expect(reduce(open, { kind: "sessionDeleted", sessionId: "other", fallbackSessionId: "f" }).arrival).toBe(1);
    expect(run([{ kind: "open" }, submit("hi"), { kind: "toggleSwitcher", announce: false }]).arrival).toBe(0);
  });

  it("gives every chat its own draft: a swap parks one and hands over the other", () => {
    const listed = reduce(createInitialState("boot"), {
      kind: "sessionsLoaded",
      sessions: [summary("chat-7")],
    });
    const typed = reduce(listed, { kind: "draft", text: "half a question" });
    expect(draftOf(typed.drafts, "boot")).toBe("half a question");
    const arrived = reduce(typed, {
      kind: "openSession",
      sessionId: "chat-7",
      messages: [],
      announce: true,
    });
    expect(draftOf(arrived.drafts, "chat-7")).toBe("");
    expect(draftOf(arrived.drafts, "boot")).toBe("half a question");
    const both = reduce(arrived, { kind: "draft", text: "a second thought" });
    const back = reduce(both, { kind: "openSession", sessionId: "boot", messages: [], announce: true });
    expect(draftOf(back.drafts, "boot")).toBe("half a question");
    expect(draftOf(back.drafts, "chat-7")).toBe("a second thought");
  });

  it("leaves a draft behind for the chat it belongs to when a fresh chat is minted", () => {
    const typed = reduce(createInitialState("boot"), { kind: "draft", text: "half a question" });
    for (const announce of [true, false]) {
      const minted = reduce(typed, { kind: "newChat", sessionId: "fresh", announce });
      expect(draftOf(minted.drafts, "fresh")).toBe("");
      expect(draftOf(minted.drafts, "boot")).toBe("half a question");
    }
  });

  it("takes a deleted chat's draft with it, whether or not that chat was the one on screen", () => {
    const listed = reduce(createInitialState("boot"), {
      kind: "sessionsLoaded",
      sessions: [summary("chat-7"), summary("chat-8")],
    });
    const here = reduce(listed, { kind: "draft", text: "about the open chat" });
    const there = reduce(
      reduce(reduce(here, { kind: "openSession", sessionId: "chat-8", messages: [], announce: false }), {
        kind: "draft",
        text: "about another chat",
      }),
      { kind: "openSession", sessionId: "boot", messages: [], announce: false },
    );
    const other = reduce(there, { kind: "sessionDeleted", sessionId: "chat-8", fallbackSessionId: "f" });
    expect(draftOf(other.drafts, "chat-8")).toBe("");
    expect(draftOf(other.drafts, "boot")).toBe("about the open chat");
    const open = reduce(there, { kind: "sessionDeleted", sessionId: "boot", fallbackSessionId: "f" });
    expect(draftOf(open.drafts, "boot")).toBe("");
    expect(draftOf(open.drafts, "f")).toBe("");
    expect(draftOf(open.drafts, "chat-8")).toBe("about another chat");
  });

  it("spends the draft it sent and leaves any other text alone", () => {
    const typed = reduce(reduce(createInitialState("boot"), { kind: "open" }), {
      kind: "draft",
      text: "half a question",
    });
    expect(draftOf(reduce(typed, submit("half a question")).drafts, "boot")).toBe("");
    const chipped = reduce(typed, submit("Summarize my unread email"));
    expect(draftOf(chipped.drafts, "boot")).toBe("half a question");
    expect(draftOf(reduce(typed, submit("   ")).drafts, "boot")).toBe("half a question");
    expect(draftOf(reduce(chipped, submit("half a question")).drafts, "boot")).toBe("half a question");
  });

  it("counts typing as touching the overlay, so a cold-start restore cannot swap under a sentence", () => {
    const typed = reduce(createInitialState("boot"), { kind: "draft", text: "half a question" });
    expect(typed.touched).toBe(true);
    const adopted = reduce(typed, { kind: "adoptSession", sessionId: "chat-7", messages: [] });
    expect(adopted.sessionId).toBe("boot");
    expect(draftOf(adopted.drafts, "boot")).toBe("half a question");
  });

  it("adoptSession hydrates like openSession but keeps the overlay hidden", () => {
    const messages: SessionMessage[] = [
      { role: "user", text: "about cats", turnId: "t", atUnixMs: 1 },
      { role: "assistant", text: "cats are great", turnId: "t", atUnixMs: 2 },
    ];
    const adopted = reduce(initialState, { kind: "adoptSession", sessionId: "chat-7", messages });
    expect(adopted.mode).toBe("hidden");
    expect(adopted.notice).toBeNull();
    expect(adopted.arrival).toBe(0);
    expect(adopted.sessionId).toBe("chat-7");
    expect(adopted.title).toBe("about cats");
    expect(adopted.seq).toBe(2);
    expect(adopted.messages.map((m) => [m.role, m.content, m.streaming])).toEqual([
      ["user", "about cats", false],
      ["assistant", "cats are great", false],
    ]);
  });

  it("adoptSession shows the most recent chat's switcher title, not a re-derived one", () => {
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
    const chatting = run([{ kind: "open" }, submit("q"), { kind: "dismiss" }]);
    const adopt: Action = { kind: "adoptSession", sessionId: "chat-7", messages: [] };
    expect(reduce(chatting, adopt)).toBe(chatting);
  });

  it("adoptSession is a no-op on an explicitly minted fresh chat that looks pristine", () => {
    const cleared = run([{ kind: "open" }, { kind: "newChat", sessionId: "n-2", announce: false }, { kind: "dismiss" }]);
    expect(cleared.mode).toBe("hidden");
    expect(cleared.messages).toEqual([]);
    expect(cleared.seq).toBe(0);
    expect(cleared.sessionId).toBe("n-2");
    const adopt: Action = { kind: "adoptSession", sessionId: "chat-7", messages: [] };
    expect(reduce(cleared, adopt)).toBe(cleared);
    expect(cleared.sessionId).toBe("n-2");
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
    expect(after.messages).toBe(stopped.messages);
    expect(after.pendingConfirm).toBeNull();
  });

  it("confirmRequest while minimized surfaces the preview, like a completed turn", () => {
    const s = run([{ kind: "open" }, submit("send it"), { kind: "dismiss" }, confirmRequest]);
    expect(s.mode).toBe("preview");
    expect(s.pendingConfirm?.confirmId).toBe("c-1");
  });

  it("confirmResolved closes the card the brain stopped waiting on", () => {
    const pending = run([{ kind: "open" }, submit("send it"), confirmRequest]);
    const resolved = reduce(pending, {
      kind: "event",
      event: { kind: "confirmResolved", confirmId: "c-1", outcome: "timeout" },
    });
    expect(resolved.pendingConfirm).toBeNull();
    expect(isTurnActive(resolved)).toBe(true);
  });

  it("confirmResolved for another id leaves the card alone", () => {
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
      { kind: "newChat", sessionId: "next", announce: false },
      { kind: "openSession", sessionId: "other", messages: [], announce: false },
    ];
    for (const ender of enders) {
      expect(reduce(pending, ender).pendingConfirm).toBeNull();
    }
  });

  it("previewFade waits out a pending approval AND a still-streaming turn", () => {
    const pending = run([{ kind: "open" }, submit("send it"), { kind: "dismiss" }, confirmRequest]);
    expect(pending.mode).toBe("preview");
    expect(reduce(pending, { kind: "previewFade" })).toBe(pending);
    const resolved = reduce(pending, { kind: "confirmAnswered", approved: true });
    expect(reduce(resolved, { kind: "previewFade" })).toBe(resolved);
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
    const again = reduce(dismissed, { kind: "reminderDismissed", reminderId: "r-1" });
    expect(again.reminders.map((r) => r.reminderId)).toEqual(["r-2"]);
  });

  it("a reminder leaving the stack says so too, and the last one says the stack is empty", () => {
    const loaded = reduce(initialState, {
      kind: "remindersLoaded",
      reminders: [reminder("r-1"), reminder("r-2")],
    });
    const one = reduce(loaded, { kind: "reminderDismissed", reminderId: "r-1" });
    expect(one.notice).toEqual({ text: "Reminder dismissed. 1 reminder left.", count: 1 });
    const none = reduce(one, { kind: "reminderDismissed", reminderId: "r-2" });
    expect(none.notice).toEqual({ text: "Reminder dismissed. No reminders left.", count: 2 });
    expect(reduce(none, { kind: "reminderDismissed", reminderId: "r-2" }).notice).toBe(none.notice);
  });

  it("reminders survive the turn and chat actions that clear other surfaces", () => {
    const loaded = reduce(initialState, { kind: "remindersLoaded", reminders: [reminder("r-1")] });
    const fresh = reduce(loaded, { kind: "newChat", sessionId: "s2", announce: false });
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

  const capture = (state: OverlayState): OverlayState =>
    reduce(state, {
      kind: "event",
      event: { kind: "toolActivity", toolName: "capture_screen", summary: "primary display" },
    });

  const settle = (state: OverlayState, ok: boolean): OverlayState =>
    reduce(state, {
      kind: "event",
      event: { kind: "toolOutcome", toolName: "capture_screen", ok },
    });

  const settleOther = (state: OverlayState): OverlayState =>
    reduce(state, {
      kind: "event",
      event: { kind: "toolOutcome", toolName: "get_volume", ok: true },
    });

  it("claims only the ask when the assistant goes for the screen", () => {
    const before = streaming();
    expect(before.capture).toBeNull();
    expect(capture(before).capture).toBe("asked");
  });

  it("climbs to read only when the outcome says the dispatch reached something", () => {
    expect(settle(capture(streaming()), true).capture).toBe("read");
  });

  it("stays at the ask when the capture did not reach the model", () => {
    expect(settle(capture(streaming()), false).capture).toBe("asked");
  });

  it("never falls a rung mid-turn, whatever order the events arrive in", () => {
    const rung = (state: OverlayState): number =>
      state.capture === null ? 0 : state.capture === "asked" ? 1 : 2;
    const mid: readonly TurnEvent[] = [
      { kind: "toolActivity", toolName: "capture_screen", summary: "primary display" },
      { kind: "toolOutcome", toolName: "capture_screen", ok: true },
      { kind: "toolActivity", toolName: "capture_screen", summary: "primary display" },
      { kind: "toolOutcome", toolName: "capture_screen", ok: false },
      { kind: "toolActivity", toolName: "get_volume", summary: "reading" },
      { kind: "toolOutcome", toolName: "get_volume", ok: false },
      { kind: "delta", text: "I could not see your screen." },
      { kind: "status", state: "thinking", detail: "hmm" },
    ];
    let state = streaming();
    for (const event of mid) {
      const next = reduce(state, { kind: "event", event });
      expect(rung(next)).toBeGreaterThanOrEqual(rung(state));
      state = next;
    }
    expect(state.capture).toBe("read");
  });

  it("stays lit for the rest of the turn, past later tool activity", () => {
    const later = reduce(capture(streaming()), {
      kind: "event",
      event: { kind: "toolActivity", toolName: "get_volume", summary: "reading" },
    });
    expect(later.capture).toBe("asked");
    expect(later.messages.at(-1)?.tool).toBe("get_volume: reading");
  });

  it("takes a read outcome even for an ask it never saw", () => {
    expect(settle(streaming(), true).capture).toBe("read");
  });

  it("stays dark for a turn that only ran other tools", () => {
    const after = reduce(streaming(), {
      kind: "event",
      event: { kind: "toolActivity", toolName: "get_volume", summary: "reading" },
    });
    expect(after.capture).toBeNull();
    expect(settleOther(after).capture).toBeNull();
  });

  it("goes out when the turn completes", () => {
    const done = reduce(settle(capture(streaming()), true), {
      kind: "event",
      event: { kind: "complete", turnId: "t1" },
    });
    expect(done.capture).toBeNull();
  });

  it("goes out when the turn fails", () => {
    const dead = reduce(capture(streaming()), {
      kind: "event",
      event: { kind: "failed", code: "INTERNAL", message: "boom" },
    });
    expect(dead.capture).toBeNull();
  });
});
