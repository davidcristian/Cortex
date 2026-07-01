import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { FakeBridge } from "../bridge/fakeBridge";
import { useOverlay } from "./useOverlay";

describe("useOverlay", () => {
  beforeEach(() => vi.useFakeTimers());
  afterEach(() => vi.useRealTimers());

  it("submits a turn and streams events into state", () => {
    const bridge = new FakeBridge();
    const { result } = renderHook(() => useOverlay(bridge, "s1"));
    act(() => result.current.open());
    expect(result.current.state.mode).toBe("panel");
    act(() => result.current.submit("hello"));
    expect(bridge.calls).toEqual([{ sessionId: "s1", text: "hello" }]);
    act(() => bridge.emit({ kind: "delta", text: "hi" }));
    expect(result.current.state.messages.at(-1)?.content).toBe("hi");
  });

  it("ignores empty and mid-stream submits", () => {
    const bridge = new FakeBridge();
    const { result } = renderHook(() => useOverlay(bridge, "s1"));
    act(() => result.current.submit("   "));
    expect(bridge.calls).toHaveLength(0);
    act(() => result.current.submit("one"));
    act(() => result.current.submit("two"));
    expect(bridge.calls).toHaveLength(1);
  });

  it("minimizes mid-stream, then a completion surfaces the preview and it auto-fades", () => {
    const bridge = new FakeBridge();
    const { result } = renderHook(() => useOverlay(bridge, "s1"));
    act(() => result.current.submit("q"));
    act(() => result.current.dismiss());
    expect(result.current.state.mode).toBe("orb");
    act(() => bridge.emit({ kind: "complete", turnId: "t" }));
    expect(result.current.state.mode).toBe("preview");
    act(() => vi.advanceTimersByTime(6000));
    expect(result.current.state.mode).toBe("hidden");
  });

  it("surfaces a transport error onto the message", () => {
    const bridge = new FakeBridge();
    const { result } = renderHook(() => useOverlay(bridge, "s1"));
    act(() => result.current.submit("q"));
    act(() => bridge.fail({ kind: "connection", message: "down" }));
    expect(result.current.state.messages.at(-1)?.error).toBe("down");
  });

  it("dismiss hides when idle", () => {
    const bridge = new FakeBridge();
    const { result } = renderHook(() => useOverlay(bridge, "s1"));
    act(() => result.current.open());
    act(() => result.current.dismiss());
    expect(result.current.state.mode).toBe("hidden");
  });

  it("newChat cancels any in-flight turn and clears (no-op cancel when none)", () => {
    const bridge = new FakeBridge();
    const { result } = renderHook(() => useOverlay(bridge, "s1"));
    act(() => result.current.newChat());
    act(() => result.current.submit("q"));
    act(() => result.current.newChat());
    expect(result.current.state.messages).toEqual([]);
    act(() => bridge.emit({ kind: "delta", text: "late" }));
    expect(result.current.state.messages).toEqual([]);
  });
});
