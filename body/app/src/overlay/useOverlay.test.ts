import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { FakeBridge } from "../bridge/fakeBridge";
import type { SessionSummary } from "../bridge/types";
import { isTurnActive } from "./overlayState";
import { useOverlay } from "./useOverlay";

const summary = (sessionId: string): SessionSummary => ({
  sessionId,
  title: `title ${sessionId}`,
  preview: `preview ${sessionId}`,
  lastActivityUnixMs: 1000,
  hoisted: false,
});

const confirmRequest = (confirmId: string) =>
  ({
    kind: "confirmRequest",
    confirmId,
    toolName: "send_email",
    argumentsJson: '{"to":"ada@example.com"}',
    reason: "outbound",
  }) as const;

/** Flush the microtasks a bridge read (`listSessions`/`sessionMessages`) resolves on. */
async function flush(): Promise<void> {
  await act(async () => {});
}

/** A deterministic session-id factory: "s0", "s1", … for successive new chats. */
function idFactory(): () => string {
  let n = 0;
  return () => `s${n++}`;
}

describe("useOverlay", () => {
  beforeEach(() => vi.useFakeTimers());
  afterEach(() => vi.useRealTimers());

  it("submits a turn against the current session and streams events into state", async () => {
    const bridge = new FakeBridge();
    const { result } = renderHook(() => useOverlay(bridge, () => "s1"));
    await flush();
    act(() => result.current.open());
    expect(result.current.state.mode).toBe("panel");
    act(() => result.current.submit("hello"));
    expect(bridge.calls).toEqual([{ sessionId: "s1", text: "hello" }]);
    act(() => bridge.emit({ kind: "delta", text: "hi" }));
    expect(result.current.state.messages.at(-1)?.content).toBe("hi");
  });

  it("ignores empty and mid-stream submits", async () => {
    const bridge = new FakeBridge();
    const { result } = renderHook(() => useOverlay(bridge, () => "s1"));
    await flush();
    act(() => result.current.submit("   "));
    expect(bridge.calls).toHaveLength(0);
    act(() => result.current.submit("one"));
    act(() => result.current.submit("two"));
    expect(bridge.calls).toHaveLength(1);
  });

  it("minimizes mid-stream, then a completion surfaces the preview and it auto-fades", async () => {
    const bridge = new FakeBridge();
    const { result } = renderHook(() => useOverlay(bridge, () => "s1"));
    await flush();
    act(() => result.current.submit("q"));
    act(() => result.current.dismiss());
    expect(result.current.state.mode).toBe("orb");
    act(() => bridge.emit({ kind: "complete", turnId: "t" }));
    expect(result.current.state.mode).toBe("preview");
    act(() => vi.advanceTimersByTime(6000));
    expect(result.current.state.mode).toBe("hidden");
  });

  it("stop cancels the stream and ends the turn in place", async () => {
    const bridge = new FakeBridge();
    const { result } = renderHook(() => useOverlay(bridge, () => "s1"));
    await flush();
    act(() => result.current.submit("q"));
    expect(isTurnActive(result.current.state)).toBe(true);
    act(() => result.current.stop());
    expect(isTurnActive(result.current.state)).toBe(false);
    act(() => bridge.emit({ kind: "delta", text: "late" }));
    expect(result.current.state.messages.at(-1)?.content).toBe("");
    expect(result.current.state.mode).toBe("panel");
  });

  it("surfaces a transport error onto the message", async () => {
    const bridge = new FakeBridge();
    const { result } = renderHook(() => useOverlay(bridge, () => "s1"));
    await flush();
    act(() => result.current.submit("q"));
    act(() => bridge.fail({ kind: "connection", message: "down" }));
    expect(result.current.state.messages.at(-1)?.error).toBe("down");
  });

  it("dismiss hides when idle", async () => {
    const bridge = new FakeBridge();
    const { result } = renderHook(() => useOverlay(bridge, () => "s1"));
    await flush();
    act(() => result.current.open());
    act(() => result.current.dismiss());
    expect(result.current.state.mode).toBe("hidden");
  });

  it("newChat cancels any in-flight turn, clears, and mints a fresh session id", async () => {
    const bridge = new FakeBridge();
    const nextId = idFactory();
    const { result } = renderHook(() => useOverlay(bridge, nextId));
    await flush();
    expect(result.current.state.sessionId).toBe("s0");
    act(() => result.current.submit("q"));
    act(() => result.current.newChat(false));
    expect(result.current.state.messages).toEqual([]);
    expect(result.current.state.sessionId).toBe("s1");
    act(() => bridge.emit({ kind: "delta", text: "late" }));
    expect(result.current.state.messages).toEqual([]);
  });

  it("loads the chat list on mount and refreshes it when a turn completes", async () => {
    const bridge = new FakeBridge();
    bridge.sessions = [summary("a")];
    const { result } = renderHook(() => useOverlay(bridge, () => "s1"));
    await flush();
    expect(result.current.state.sessions).toEqual([summary("a")]);
    act(() => result.current.submit("q"));
    bridge.sessions = [summary("a"), summary("b")];
    act(() => bridge.emit({ kind: "complete", turnId: "t" }));
    await flush();
    expect(result.current.state.sessions).toEqual([summary("a"), summary("b")]);
  });

  it("refreshes the chat list on each summon, so a list that failed while hidden fills in", async () => {
    const bridge = new FakeBridge();
    bridge.listFails = true;
    const { result } = renderHook(() => useOverlay(bridge, () => "s1"));
    await flush();
    expect(result.current.state.sessions).toEqual([]);
    expect(bridge.listCalls).toBe(1);

    bridge.listFails = false;
    bridge.sessions = [summary("a")];
    act(() => result.current.open());
    await flush();
    expect(bridge.listCalls).toBe(2);
    expect(result.current.state.sessions).toEqual([summary("a")]);
  });

  it("does not re-list while the overlay stays visible, and lists again on the next summon", async () => {
    const bridge = new FakeBridge();
    const { result } = renderHook(() => useOverlay(bridge, () => "s1"));
    await flush();
    act(() => result.current.open());
    await flush();
    expect(bridge.listCalls).toBe(2);

    act(() => result.current.submit("q"));
    act(() => result.current.dismiss());
    expect(result.current.state.mode).toBe("orb");
    act(() => result.current.open());
    await flush();
    expect(bridge.listCalls).toBe(2);

    act(() => result.current.stop());
    await flush();
    const afterTurn = bridge.listCalls;
    act(() => result.current.dismiss());
    expect(result.current.state.mode).toBe("hidden");
    act(() => result.current.open());
    await flush();
    expect(bridge.listCalls).toBe(afterTurn + 1);
  });

  it("probes the brain connection on summon, and not while hidden", async () => {
    const bridge = new FakeBridge();
    bridge.link = { state: "degraded", detail: "store down" };
    const { result } = renderHook(() => useOverlay(bridge, () => "s1"));
    await flush();
    expect(result.current.state.link).toEqual({ state: "unknown", detail: "", probing: false });
    expect(bridge.linkCalls).toBe(0);

    act(() => result.current.open());
    await flush();
    expect(result.current.state.link).toEqual({
      state: "degraded",
      detail: "store down",
      probing: false,
    });
  });

  it("keeps the indicator current from the turn itself, with no probe", async () => {
    const bridge = new FakeBridge();
    bridge.link = { state: "down", detail: "refused" };
    const { result } = renderHook(() => useOverlay(bridge, () => "s1"));
    act(() => result.current.open());
    await flush();
    expect(result.current.state.link.state).toBe("down");
    const probes = bridge.linkCalls;

    act(() => result.current.submit("q"));
    act(() => bridge.emit({ kind: "delta", text: "hi" }));
    expect(result.current.state.link).toEqual({ state: "ready", detail: "", probing: false });
    expect(bridge.linkCalls).toBe(probes);

    act(() => bridge.fail({ kind: "connection", message: "brain went away" }));
    expect(result.current.state.link).toEqual({
      state: "down",
      detail: "brain went away",
      probing: false,
    });
    expect(bridge.linkCalls).toBe(probes);
  });

  it("a failed session list leaves the current list untouched", async () => {
    const bridge = new FakeBridge();
    bridge.listFails = true;
    const { result } = renderHook(() => useOverlay(bridge, () => "s1"));
    await flush();
    expect(result.current.state.sessions).toEqual([]);
  });

  it("adopts the most recent chat on cold start, staying hidden, with its switcher title", async () => {
    const bridge = new FakeBridge();
    bridge.sessions = [
      { sessionId: "recent", title: "Everything about cats", preview: "p", lastActivityUnixMs: 1000, hoisted: false },
      summary("older"),
    ];
    bridge.messagesBySession = {
      recent: [{ role: "user", text: "where we left off", turnId: "t", atUnixMs: 1 }],
    };
    const { result } = renderHook(() => useOverlay(bridge, () => "s1"));
    await flush();
    expect(result.current.state.sessionId).toBe("recent");
    expect(result.current.state.title).toBe("Everything about cats");
    expect(result.current.state.mode).toBe("hidden");
  });

  it("a failed cold-start history load leaves the fresh chat", async () => {
    const bridge = new FakeBridge();
    bridge.sessions = [summary("recent")];
    bridge.messagesFail = true;
    const { result } = renderHook(() => useOverlay(bridge, () => "s1"));
    await flush();
    expect(result.current.state.sessionId).toBe("s1");
  });

  it("attempts cold-start adoption once: a later newest-session change re-fetches nothing", async () => {
    const bridge = new FakeBridge();
    bridge.sessions = [summary("recent")];
    bridge.messagesFail = true;
    const { result } = renderHook(() => useOverlay(bridge, () => "s1"));
    await flush();
    expect(bridge.messagesCalls).toEqual(["recent"]);

    bridge.messagesFail = false;
    act(() => result.current.submit("q"));
    bridge.sessions = [summary("fresh"), summary("recent")];
    act(() => bridge.emit({ kind: "complete", turnId: "t" }));
    await flush();
    expect(bridge.messagesCalls).toEqual(["recent"]);
    expect(result.current.state.sessionId).toBe("s1");
  });

  it("a submit racing the cold-start restore wins; adoption backs off", async () => {
    const bridge = new FakeBridge();
    bridge.sessions = [summary("recent")];
    bridge.messagesBySession = {
      recent: [{ role: "user", text: "stored", turnId: "t", atUnixMs: 1 }],
    };
    const { result } = renderHook(() => useOverlay(bridge, () => "s1"));
    act(() => result.current.open());
    act(() => result.current.submit("racing turn"));
    await flush();
    expect(result.current.state.sessionId).toBe("s1");
    expect(result.current.state.messages.at(0)?.content).toBe("racing turn");
  });

  it("openSession cancels any in-flight turn, loads history, and switches to it", async () => {
    const bridge = new FakeBridge();
    bridge.messagesBySession = {
      "chat-2": [{ role: "user", text: "old question", turnId: "t", atUnixMs: 1 }],
    };
    const { result } = renderHook(() => useOverlay(bridge, () => "s1"));
    await flush();
    act(() => result.current.submit("q"));
    act(() => result.current.openSession("chat-2", false));
    await flush();
    expect(result.current.state.sessionId).toBe("chat-2");
    expect(result.current.state.messages.at(0)?.content).toBe("old question");
  });

  it("opening a session with no stored history falls back to a fresh panel", async () => {
    const bridge = new FakeBridge();
    const { result } = renderHook(() => useOverlay(bridge, () => "s1"));
    await flush();
    act(() => result.current.openSession("ghost", false));
    await flush();
    expect(result.current.state.sessionId).toBe("ghost");
    expect(result.current.state.messages).toEqual([]);
    expect(result.current.state.title).toBe("New chat");
  });

  it("a failed history load leaves the current chat in place", async () => {
    const bridge = new FakeBridge();
    bridge.messagesFail = true;
    const { result } = renderHook(() => useOverlay(bridge, () => "s1"));
    await flush();
    act(() => result.current.openSession("chat-2", false));
    await flush();
    expect(result.current.state.sessionId).toBe("s1");
  });

  it("renameSession writes the label and re-lists so the switcher shows the new title", async () => {
    const bridge = new FakeBridge();
    bridge.sessions = [summary("chat-2"), summary("chat-3")];
    const { result } = renderHook(() => useOverlay(bridge, () => "s1"));
    await flush();
    const listsBefore = bridge.listCalls;
    act(() => result.current.renameSession("chat-2", "Everything about cats"));
    await flush();
    expect(bridge.renames).toEqual([{ sessionId: "chat-2", title: "Everything about cats" }]);
    expect(bridge.listCalls).toBe(listsBefore + 1);
    const relisted = result.current.state.sessions;
    expect(relisted.find((s) => s.sessionId === "chat-2")?.title).toBe("Everything about cats");
    expect(relisted.find((s) => s.sessionId === "chat-3")?.title).toBe("title chat-3");
  });

  it("a failed rename is swallowed and leaves the chat list unchanged", async () => {
    const bridge = new FakeBridge();
    bridge.sessions = [summary("chat-2")];
    bridge.renameFails = true;
    const { result } = renderHook(() => useOverlay(bridge, () => "s1"));
    await flush();
    const listsBefore = bridge.listCalls;
    act(() => result.current.renameSession("chat-2", "new"));
    await flush();
    expect(bridge.renames).toEqual([{ sessionId: "chat-2", title: "new" }]);
    expect(bridge.listCalls).toBe(listsBefore);
    expect(result.current.state.sessions.find((s) => s.sessionId === "chat-2")?.title).toBe(
      "title chat-2",
    );
  });

  it("deleteSession removes another chat and re-lists so the switcher drops it", async () => {
    const bridge = new FakeBridge();
    bridge.sessions = [summary("a"), summary("b")];
    const nextId = idFactory();
    const { result } = renderHook(() => useOverlay(bridge, nextId));
    await flush();
    expect(result.current.state.sessionId).toBe("a");
    const listsBefore = bridge.listCalls;
    act(() => result.current.deleteSession("b"));
    await flush();
    expect(bridge.deletes).toEqual(["b"]);
    expect(bridge.listCalls).toBe(listsBefore + 1);
    expect(result.current.state.sessions.map((s) => s.sessionId)).toEqual(["a"]);
    expect(result.current.state.sessionId).toBe("a");
  });

  it("deleteSession on the open chat denies a pending confirm, cancels its turn, and resets", async () => {
    const bridge = new FakeBridge();
    bridge.sessions = [summary("open")];
    const nextId = idFactory();
    const { result } = renderHook(() => useOverlay(bridge, nextId));
    await flush();
    expect(result.current.state.sessionId).toBe("open");
    act(() => result.current.open());
    act(() => result.current.submit("a question"));
    act(() => bridge.emit(confirmRequest("c-9")));
    expect(result.current.state.pendingConfirm?.confirmId).toBe("c-9");
    act(() => result.current.deleteSession("open"));
    await flush();
    expect(bridge.confirms).toEqual([{ confirmId: "c-9", approved: false }]);
    expect(bridge.deletes).toEqual(["open"]);
    expect(result.current.state.sessionId).not.toBe("open");
    expect(result.current.state.messages).toEqual([]);
    expect(result.current.state.pendingConfirm).toBeNull();
    expect(isTurnActive(result.current.state)).toBe(false);
  });

  it("a failed delete is swallowed and leaves the chat and list unchanged", async () => {
    const bridge = new FakeBridge();
    bridge.sessions = [summary("a"), summary("b")];
    bridge.deleteFails = true;
    const nextId = idFactory();
    const { result } = renderHook(() => useOverlay(bridge, nextId));
    await flush();
    const listsBefore = bridge.listCalls;
    const sessionsBefore = result.current.state.sessions;
    act(() => result.current.deleteSession("b"));
    await flush();
    expect(bridge.deletes).toEqual(["b"]);
    expect(bridge.listCalls).toBe(listsBefore);
    expect(result.current.state.sessions).toBe(sessionsBefore);
  });

  it("setSessionHoisted writes the flag and re-lists so the switcher re-groups hoisted-first", async () => {
    const bridge = new FakeBridge();
    bridge.sessions = [
      { ...summary("recent"), lastActivityUnixMs: 2000 },
      { ...summary("old"), lastActivityUnixMs: 1000 },
    ];
    const { result } = renderHook(() => useOverlay(bridge, () => "s1"));
    await flush();
    const listsBefore = bridge.listCalls;
    act(() => result.current.setSessionHoisted("old", true));
    await flush();
    expect(bridge.hoists).toEqual([{ sessionId: "old", hoisted: true }]);
    expect(bridge.listCalls).toBe(listsBefore + 1);
    const relisted = result.current.state.sessions;
    expect(relisted.map((s) => s.sessionId)).toEqual(["old", "recent"]);
    expect(relisted[0]?.hoisted).toBe(true);
  });

  it("a failed hoist is swallowed and leaves the chat list unchanged", async () => {
    const bridge = new FakeBridge();
    bridge.sessions = [summary("a")];
    bridge.hoistFails = true;
    const { result } = renderHook(() => useOverlay(bridge, () => "s1"));
    await flush();
    const listsBefore = bridge.listCalls;
    const sessionsBefore = result.current.state.sessions;
    act(() => result.current.setSessionHoisted("a", true));
    await flush();
    expect(bridge.hoists).toEqual([{ sessionId: "a", hoisted: true }]);
    expect(bridge.listCalls).toBe(listsBefore);
    expect(result.current.state.sessions).toBe(sessionsBefore);
  });

  it("cycles to newer/older chats and no-ops at the ends", async () => {
    const bridge = new FakeBridge();
    bridge.sessions = [summary("newest"), summary("oldest")];
    bridge.messagesBySession = {
      newest: [{ role: "user", text: "newest chat", turnId: "t", atUnixMs: 1 }],
      oldest: [{ role: "user", text: "oldest chat", turnId: "t", atUnixMs: 1 }],
    };
    const { result } = renderHook(() => useOverlay(bridge, () => "s1"));
    await flush();
    expect(result.current.state.sessionId).toBe("newest");
    act(() => result.current.cycleNext());
    await flush();
    expect(result.current.state.sessionId).toBe("oldest");
    act(() => result.current.cyclePrev());
    await flush();
    expect(result.current.state.sessionId).toBe("newest");
    act(() => result.current.cyclePrev());
    await flush();
    expect(result.current.state.sessionId).toBe("newest");
    act(() => result.current.cycleNext());
    await flush();
    act(() => result.current.cycleNext());
    await flush();
    expect(result.current.state.sessionId).toBe("oldest");
  });

  it("a cycled chat is announced by name and a picked one is not", async () => {
    const bridge = new FakeBridge();
    bridge.sessions = [summary("newest"), summary("oldest")];
    bridge.messagesBySession = {
      newest: [{ role: "user", text: "newest chat", turnId: "t", atUnixMs: 1 }],
      oldest: [{ role: "user", text: "oldest chat", turnId: "t", atUnixMs: 1 }],
    };
    const { result } = renderHook(() => useOverlay(bridge, () => "s1"));
    await flush();
    expect(result.current.state.notice).toBeNull();
    act(() => result.current.cycleNext());
    await flush();
    expect(result.current.state.notice?.text).toContain(result.current.state.title);
    expect(result.current.state.notice).toEqual({ text: "Switched to title oldest.", count: 1 });
    act(() => result.current.cyclePrev());
    await flush();
    expect(result.current.state.notice).toEqual({ text: "Switched to title newest.", count: 2 });
    act(() => result.current.openSession("oldest", false));
    await flush();
    expect(result.current.state.sessionId).toBe("oldest");
    expect(result.current.state.notice).toBeNull();
  });

  it("answers a pending confirm over the bridge and clears the card", async () => {
    const bridge = new FakeBridge();
    const { result } = renderHook(() => useOverlay(bridge, () => "s1"));
    await flush();
    act(() => result.current.submit("send it"));
    act(() => bridge.emit(confirmRequest("c-1")));
    expect(result.current.state.pendingConfirm?.confirmId).toBe("c-1");
    act(() => result.current.respondConfirm("c-1", true));
    expect(bridge.confirms).toEqual([{ confirmId: "c-1", approved: true }]);
    expect(result.current.state.pendingConfirm).toBeNull();
  });

  it("a deny answer crosses the bridge as approved: false", async () => {
    const bridge = new FakeBridge();
    const { result } = renderHook(() => useOverlay(bridge, () => "s1"));
    await flush();
    act(() => result.current.submit("send it"));
    act(() => bridge.emit(confirmRequest("c-1")));
    act(() => result.current.respondConfirm("c-1", false));
    expect(bridge.confirms).toEqual([{ confirmId: "c-1", approved: false }]);
    expect(result.current.state.pendingConfirm).toBeNull();
  });

  it("ignores answers with no pending confirm, a stale id, or a duplicate click", async () => {
    const bridge = new FakeBridge();
    const { result } = renderHook(() => useOverlay(bridge, () => "s1"));
    await flush();
    act(() => result.current.respondConfirm("c-0", true));
    expect(bridge.confirms).toHaveLength(0);
    act(() => result.current.submit("send it"));
    act(() => bridge.emit(confirmRequest("c-1")));
    act(() => result.current.respondConfirm("c-9", true));
    expect(bridge.confirms).toHaveLength(0);
    act(() => result.current.respondConfirm("c-1", true));
    act(() => result.current.respondConfirm("c-1", true));
    expect(bridge.confirms).toEqual([{ confirmId: "c-1", approved: true }]);
  });

  it("a brain-resolved confirm closes the card and swallows the click that follows", async () => {
    const bridge = new FakeBridge();
    const { result } = renderHook(() => useOverlay(bridge, () => "s1"));
    await flush();
    act(() => result.current.submit("send it"));
    act(() => bridge.emit(confirmRequest("c-1")));
    act(() =>
      bridge.emit({ kind: "confirmResolved", confirmId: "c-1", outcome: "timeout" }),
    );
    expect(result.current.state.pendingConfirm).toBeNull();
    act(() => result.current.respondConfirm("c-1", true));
    act(() => result.current.stop());
    expect(bridge.confirms).toHaveLength(0);
  });

  it("a lost confirm answer is non-fatal. The card still closes (deny-by-timeout brain-side)", async () => {
    const bridge = new FakeBridge();
    bridge.confirmFails = true;
    const { result } = renderHook(() => useOverlay(bridge, () => "s1"));
    await flush();
    act(() => result.current.submit("send it"));
    act(() => bridge.emit(confirmRequest("c-1")));
    act(() => result.current.respondConfirm("c-1", true));
    await flush();
    expect(result.current.state.pendingConfirm).toBeNull();
  });

  it("stop denies a pending confirm over the bridge (no zombie turn), then ends the turn", async () => {
    const bridge = new FakeBridge();
    const { result } = renderHook(() => useOverlay(bridge, () => "s1"));
    await flush();
    act(() => result.current.submit("send it"));
    act(() => bridge.emit(confirmRequest("c-1")));
    act(() => result.current.stop());
    expect(bridge.confirms).toEqual([{ confirmId: "c-1", approved: false }]);
    expect(result.current.state.pendingConfirm).toBeNull();
  });

  it("dismiss denies a pending confirm so the hidden turn resolves immediately", async () => {
    const bridge = new FakeBridge();
    const { result } = renderHook(() => useOverlay(bridge, () => "s1"));
    await flush();
    act(() => result.current.submit("send it"));
    act(() => bridge.emit(confirmRequest("c-1")));
    act(() => result.current.dismiss());
    expect(bridge.confirms).toEqual([{ confirmId: "c-1", approved: false }]);
    expect(result.current.state.pendingConfirm).toBeNull();
  });

  it("newChat and openSession each deny a pending confirm before switching away", async () => {
    const bridge = new FakeBridge();
    bridge.messagesBySession["prior"] = [];
    const { result } = renderHook(() => useOverlay(bridge, () => "s1"));
    await flush();
    act(() => result.current.submit("send it"));
    act(() => bridge.emit(confirmRequest("c-1")));
    act(() => result.current.newChat(false));
    expect(bridge.confirms).toEqual([{ confirmId: "c-1", approved: false }]);
    act(() => result.current.submit("send again"));
    act(() => bridge.emit(confirmRequest("c-2")));
    act(() => result.current.openSession("prior", false));
    await flush();
    expect(bridge.confirms).toEqual([
      { confirmId: "c-1", approved: false },
      { confirmId: "c-2", approved: false },
    ]);
  });

  it("a turn-ending action with no pending confirm sends no deny", async () => {
    const bridge = new FakeBridge();
    const { result } = renderHook(() => useOverlay(bridge, () => "s1"));
    await flush();
    act(() => result.current.submit("plain turn"));
    act(() => result.current.stop());
    expect(bridge.confirms).toHaveLength(0);
  });

  it("the preview waits out a pending confirm and the streaming turn; fades once complete", async () => {
    const bridge = new FakeBridge();
    const { result } = renderHook(() => useOverlay(bridge, () => "s1"));
    await flush();
    act(() => result.current.submit("send it"));
    act(() => result.current.dismiss());
    act(() => bridge.emit(confirmRequest("c-1")));
    expect(result.current.state.mode).toBe("preview");
    act(() => vi.advanceTimersByTime(60_000));
    expect(result.current.state.mode).toBe("preview");
    act(() => result.current.respondConfirm("c-1", false));
    act(() => vi.advanceTimersByTime(60_000));
    expect(result.current.state.mode).toBe("preview");
    act(() => bridge.emit({ kind: "complete", turnId: "t" }));
    act(() => vi.advanceTimersByTime(6000));
    expect(result.current.state.mode).toBe("hidden");
  });

  it("defaults the session id to a freshly minted uuid", async () => {
    const bridge = new FakeBridge();
    const { result } = renderHook(() => useOverlay(bridge));
    await flush();
    expect(result.current.state.sessionId).not.toBe("");
    expect(typeof result.current.state.sessionId).toBe("string");
  });

  it("toggleSwitcher opens and closes the list", async () => {
    const bridge = new FakeBridge();
    const { result } = renderHook(() => useOverlay(bridge, () => "s1"));
    await flush();
    expect(result.current.state.switcherOpen).toBe(false);
    act(() => result.current.toggleSwitcher(false));
    expect(result.current.state.switcherOpen).toBe(true);
  });

  it("drives the console's one tab: an opener toggles it, the strip switches, Esc's close leaves", async () => {
    const bridge = new FakeBridge();
    const { result } = renderHook(() => useOverlay(bridge, () => "s1"));
    await flush();
    act(() => result.current.toggleConsole("shortcuts"));
    expect(result.current.state.consoleTab).toBe("shortcuts");
    act(() => result.current.openConsole("appearance"));
    expect(result.current.state.consoleTab).toBe("appearance");
    act(() => result.current.closeConsole());
    expect(result.current.state.consoleTab).toBeNull();
  });

  it("hovering the preview pauses the auto-fade; leaving restarts the full countdown", async () => {
    const bridge = new FakeBridge();
    const { result } = renderHook(() => useOverlay(bridge, () => "s1"));
    await flush();
    act(() => result.current.submit("q"));
    act(() => result.current.dismiss());
    act(() => bridge.emit({ kind: "complete", turnId: "t" }));
    expect(result.current.state.mode).toBe("preview");
    act(() => result.current.previewHover(true));
    act(() => vi.advanceTimersByTime(60_000));
    expect(result.current.state.mode).toBe("preview");
    act(() => result.current.previewHover(false));
    act(() => vi.advanceTimersByTime(5999));
    expect(result.current.state.mode).toBe("preview");
    act(() => vi.advanceTimersByTime(1));
    expect(result.current.state.mode).toBe("hidden");
  });

  it("the hover latch clears on leaving preview mode, so the next preview still fades", async () => {
    const bridge = new FakeBridge();
    const { result } = renderHook(() => useOverlay(bridge, () => "s1"));
    await flush();
    act(() => result.current.submit("q"));
    act(() => result.current.dismiss());
    act(() => bridge.emit({ kind: "complete", turnId: "t" }));
    act(() => result.current.previewHover(true));
    act(() => result.current.open());
    await flush();
    act(() => result.current.submit("again"));
    act(() => result.current.dismiss());
    act(() => bridge.emit({ kind: "complete", turnId: "t2" }));
    expect(result.current.state.mode).toBe("preview");
    act(() => vi.advanceTimersByTime(6000));
    expect(result.current.state.mode).toBe("hidden");
  });
});
