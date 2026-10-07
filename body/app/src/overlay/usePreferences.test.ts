import { act, renderHook, waitFor } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { FakeBridge } from "../bridge/fakeBridge";
import { MARK_KEY, THEME_KEY, WINDOW_KEY, usePreferences } from "./usePreferences";

describe("usePreferences", () => {
  it("starts with nothing chosen, so the defaults apply until the record arrives", () => {
    const bridge = new FakeBridge();
    const { result } = renderHook(() => usePreferences(bridge, false));
    expect(result.current.appearance).toEqual({ theme: null, mark: null, window: null });
  });

  it("hydrates all three choices from the brain's record", async () => {
    const bridge = new FakeBridge();
    bridge.preferences = [
      { key: THEME_KEY, value: "daylight" },
      { key: MARK_KEY, value: "tangent" },
      { key: WINDOW_KEY, value: "trance" },
    ];
    const { result } = renderHook(() => usePreferences(bridge, false));
    await waitFor(() =>
      expect(result.current.appearance).toEqual({
        theme: "daylight",
        mark: "tangent",
        window: "trance",
      }),
    );
  });

  it("ignores keys it does not own, which belong to some other surface", async () => {
    const bridge = new FakeBridge();
    bridge.preferences = [
      { key: "someone.else", value: "whatever" },
      { key: MARK_KEY, value: "hunch" },
    ];
    const { result } = renderHook(() => usePreferences(bridge, false));
    await waitFor(() => expect(result.current.appearance.mark).toBe("hunch"));
    expect(result.current.appearance.theme).toBeNull();
  });

  it("applies a choice immediately and persists it without being awaited", async () => {
    const bridge = new FakeBridge();
    const { result } = renderHook(() => usePreferences(bridge, false));
    act(() => result.current.setMark("muse"));
    expect(result.current.appearance.mark).toBe("muse");
    await waitFor(() =>
      expect(bridge.preferenceWrites).toEqual([{ key: MARK_KEY, value: "muse" }]),
    );
  });

  it("treats the window edge as the third choice, applied and persisted the same way", async () => {
    const bridge = new FakeBridge();
    const { result } = renderHook(() => usePreferences(bridge, false));
    act(() => result.current.setWindow("still"));
    expect(result.current.appearance.window).toBe("still");
    await waitFor(() =>
      expect(bridge.preferenceWrites).toEqual([{ key: WINDOW_KEY, value: "still" }]),
    );
  });

  it("writes a cleared key for 'follow the system', which is what null means", async () => {
    const bridge = new FakeBridge();
    const { result } = renderHook(() => usePreferences(bridge, false));
    act(() => result.current.setTheme("midnight"));
    act(() => result.current.setTheme(null));
    expect(result.current.appearance.theme).toBeNull();
    await waitFor(() =>
      expect(bridge.preferenceWrites).toEqual([
        { key: THEME_KEY, value: "midnight" },
        { key: THEME_KEY, value: "" },
      ]),
    );
  });

  it("never lets a late record overwrite a choice the user already made", async () => {
    const bridge = new FakeBridge();
    bridge.preferences = [
      { key: THEME_KEY, value: "daylight" },
      { key: MARK_KEY, value: "tangent" },
    ];
    let release: (() => void) | null = null;
    const paused = new Promise<void>((resolve) => {
      release = resolve;
    });
    const slow = {
      ...bridge,
      getPreferences: () => paused.then(() => bridge.getPreferences()),
      setPreference: bridge.setPreference.bind(bridge),
    } as unknown as FakeBridge;
    const { result } = renderHook(() => usePreferences(slow, false));
    act(() => result.current.setMark("hunch"));
    act(() => result.current.setWindow("reverie"));
    act(() => release?.());
    await waitFor(() => expect(result.current.appearance.theme).toBe("daylight"));
    expect(result.current.appearance.mark).toBe("hunch");
    expect(result.current.appearance.window).toBe("reverie");
  });

  it("keeps the defaults when the record cannot be read", async () => {
    const bridge = new FakeBridge();
    bridge.preferencesFail = true;
    const { result } = renderHook(() => usePreferences(bridge, false));
    await waitFor(() => expect(bridge.preferenceReads).toBe(1));
    expect(result.current.appearance).toEqual({ theme: null, mark: null, window: null });
  });

  it("keeps a choice applied when persisting it fails, losing only its durability", async () => {
    const bridge = new FakeBridge();
    bridge.preferenceWriteFails = true;
    const { result } = renderHook(() => usePreferences(bridge, false));
    act(() => result.current.setMark("tangent"));
    await waitFor(() => expect(bridge.preferenceWrites).toHaveLength(1));
    expect(result.current.appearance.mark).toBe("tangent");
  });

  it("drops a record that resolves after unmount rather than setting state on a dead hook", async () => {
    const bridge = new FakeBridge();
    bridge.preferences = [{ key: MARK_KEY, value: "tangent" }];
    let release: (() => void) | null = null;
    const paused = new Promise<void>((resolve) => {
      release = resolve;
    });
    const slow = {
      ...bridge,
      getPreferences: () => paused.then(() => bridge.getPreferences()),
      setPreference: bridge.setPreference.bind(bridge),
    } as unknown as FakeBridge;
    const { result, unmount } = renderHook(() => usePreferences(slow, false));
    unmount();
    act(() => release?.());
    await Promise.resolve();
    expect(result.current.appearance.mark).toBeNull();
  });

  it("reads the record again at the next summon after a read that failed", async () => {
    const bridge = new FakeBridge();
    bridge.preferencesFail = true;
    bridge.preferences = [{ key: WINDOW_KEY, value: "still" }];
    const { result, rerender } = renderHook(
      ({ visible }) => usePreferences(bridge, visible),
      { initialProps: { visible: false } },
    );
    await waitFor(() => expect(bridge.preferenceReads).toBe(1));
    rerender({ visible: true });
    await waitFor(() => expect(bridge.preferenceReads).toBe(2));
    expect(result.current.appearance.window).toBeNull();
    bridge.preferencesFail = false;
    rerender({ visible: false });
    rerender({ visible: true });
    await waitFor(() => expect(result.current.appearance.window).toBe("still"));
    expect(bridge.preferenceReads).toBe(3);
  });

  it("reads the record no more once a read has succeeded", async () => {
    const bridge = new FakeBridge();
    bridge.preferences = [{ key: MARK_KEY, value: "muse" }];
    const { result, rerender } = renderHook(
      ({ visible }) => usePreferences(bridge, visible),
      { initialProps: { visible: false } },
    );
    await waitFor(() => expect(result.current.appearance.mark).toBe("muse"));
    bridge.preferences = [{ key: MARK_KEY, value: "hunch" }];
    rerender({ visible: true });
    rerender({ visible: false });
    rerender({ visible: true });
    await Promise.resolve();
    expect(bridge.preferenceReads).toBe(1);
    expect(result.current.appearance.mark).toBe("muse");
  });

  it("reads the new bridge's record when the bridge changes after a read", async () => {
    const first = new FakeBridge();
    first.preferences = [{ key: MARK_KEY, value: "muse" }];
    const second = new FakeBridge();
    second.preferences = [{ key: MARK_KEY, value: "hunch" }];
    const { result, rerender } = renderHook(({ bridge }) => usePreferences(bridge, false), {
      initialProps: { bridge: first },
    });
    await waitFor(() => expect(result.current.appearance.mark).toBe("muse"));
    rerender({ bridge: second });
    await waitFor(() => expect(result.current.appearance.mark).toBe("hunch"));
  });

  it("drops the old bridge's record when it resolves after the bridge changed", async () => {
    const first = new FakeBridge();
    first.preferences = [{ key: MARK_KEY, value: "muse" }];
    let release: (() => void) | null = null;
    const paused = new Promise<void>((resolve) => {
      release = resolve;
    });
    const slow = {
      ...first,
      getPreferences: () => paused.then(() => first.getPreferences()),
      setPreference: first.setPreference.bind(first),
    } as unknown as FakeBridge;
    const second = new FakeBridge();
    second.preferences = [{ key: MARK_KEY, value: "hunch" }];
    const { result, rerender } = renderHook(({ bridge }) => usePreferences(bridge, false), {
      initialProps: { bridge: slow },
    });
    rerender({ bridge: second });
    await waitFor(() => expect(result.current.appearance.mark).toBe("hunch"));
    await act(async () => release?.());
    await waitFor(() => expect(first.preferenceReads).toBe(1));
    expect(result.current.appearance.mark).toBe("hunch");
  });
});
