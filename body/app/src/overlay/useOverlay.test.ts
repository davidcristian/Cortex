import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { FakeBridge } from "../bridge/fakeBridge";
import type { SessionSummary } from "../bridge/types";
import { useOverlay } from "./useOverlay";

const summary = (sessionId: string): SessionSummary => ({
  sessionId,
  title: `title ${sessionId}`,
  preview: `preview ${sessionId}`,
  lastActivityUnixMs: 1000,
});

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
    const nextId = idFactory(); // one stable factory across renders
    const { result } = renderHook(() => useOverlay(bridge, nextId));
    await flush();
    expect(result.current.state.sessionId).toBe("s0");
    act(() => result.current.submit("q"));
    act(() => result.current.newChat());
    expect(result.current.state.messages).toEqual([]);
    expect(result.current.state.sessionId).toBe("s1");
    // The cancelled turn's late events no longer reach the (cleared) state.
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

  it("a failed session list leaves the current list untouched", async () => {
    const bridge = new FakeBridge();
    bridge.listFails = true;
    const { result } = renderHook(() => useOverlay(bridge, () => "s1"));
    await flush();
    expect(result.current.state.sessions).toEqual([]);
  });

  it("openSession cancels any in-flight turn, loads history, and switches to it", async () => {
    const bridge = new FakeBridge();
    bridge.messagesBySession = {
      "chat-2": [{ role: "user", text: "old question", turnId: "t", atUnixMs: 1 }],
    };
    const { result } = renderHook(() => useOverlay(bridge, () => "s1"));
    await flush();
    act(() => result.current.submit("q")); // an in-flight turn openSession must cancel
    act(() => result.current.openSession("chat-2"));
    await flush();
    expect(result.current.state.sessionId).toBe("chat-2");
    expect(result.current.state.messages.at(0)?.content).toBe("old question");
  });

  it("opening a session with no stored history falls back to a fresh panel", async () => {
    const bridge = new FakeBridge(); // messagesBySession empty → resolves []
    const { result } = renderHook(() => useOverlay(bridge, () => "s1"));
    await flush();
    act(() => result.current.openSession("ghost"));
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
    act(() => result.current.openSession("chat-2"));
    await flush();
    expect(result.current.state.sessionId).toBe("s1");
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
    // s1 isn't listed → cycleNext enters the most recent saved chat.
    act(() => result.current.cycleNext());
    await flush();
    expect(result.current.state.sessionId).toBe("newest");
    // From the newest, next → oldest; prev → back to newest.
    act(() => result.current.cycleNext());
    await flush();
    expect(result.current.state.sessionId).toBe("oldest");
    act(() => result.current.cyclePrev());
    await flush();
    expect(result.current.state.sessionId).toBe("newest");
    // At the newest end, cyclePrev is a no-op (session unchanged).
    act(() => result.current.cyclePrev());
    await flush();
    expect(result.current.state.sessionId).toBe("newest");
    // At the oldest end, cycleNext is likewise a no-op.
    act(() => result.current.cycleNext());
    await flush();
    act(() => result.current.cycleNext());
    await flush();
    expect(result.current.state.sessionId).toBe("oldest");
  });

  it("defaults the session id to a freshly minted uuid", async () => {
    const bridge = new FakeBridge();
    const { result } = renderHook(() => useOverlay(bridge)); // no factory → the default
    await flush();
    expect(result.current.state.sessionId).not.toBe("");
    expect(typeof result.current.state.sessionId).toBe("string");
  });

  it("toggleSwitcher opens and closes the list", async () => {
    const bridge = new FakeBridge();
    const { result } = renderHook(() => useOverlay(bridge, () => "s1"));
    await flush();
    expect(result.current.state.switcherOpen).toBe(false);
    act(() => result.current.toggleSwitcher());
    expect(result.current.state.switcherOpen).toBe(true);
  });
});
