import { act, renderHook, waitFor } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { FakeBridge } from "../bridge/fakeBridge";
import { MARK_KEY, THEME_KEY, WINDOW_KEY, usePreferences } from "./usePreferences";

describe("usePreferences", () => {
  it("starts with nothing chosen, so the defaults apply until the record arrives", () => {
    const bridge = new FakeBridge();
    const { result } = renderHook(() => usePreferences(bridge));
    expect(result.current.appearance).toEqual({ theme: null, mark: null, window: null });
  });

  it("hydrates all three choices from the brain's record", async () => {
    const bridge = new FakeBridge();
    bridge.preferences = [
      { key: THEME_KEY, value: "daylight" },
      { key: MARK_KEY, value: "tangent" },
      { key: WINDOW_KEY, value: "trance" },
    ];
    const { result } = renderHook(() => usePreferences(bridge));
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
    const { result } = renderHook(() => usePreferences(bridge));
    await waitFor(() => expect(result.current.appearance.mark).toBe("hunch"));
    expect(result.current.appearance.theme).toBeNull();
  });

  it("applies a choice immediately and persists it without being awaited", async () => {
    const bridge = new FakeBridge();
    const { result } = renderHook(() => usePreferences(bridge));
    act(() => result.current.setMark("muse"));
    // Applied in the same tick: the UI never waits on the seam to show a choice.
    expect(result.current.appearance.mark).toBe("muse");
    await waitFor(() =>
      expect(bridge.preferenceWrites).toEqual([{ key: MARK_KEY, value: "muse" }]),
    );
  });

  it("treats the window edge as the third choice, applied and persisted the same way", async () => {
    const bridge = new FakeBridge();
    const { result } = renderHook(() => usePreferences(bridge));
    act(() => result.current.setWindow("still"));
    expect(result.current.appearance.window).toBe("still");
    await waitFor(() =>
      expect(bridge.preferenceWrites).toEqual([{ key: WINDOW_KEY, value: "still" }]),
    );
  });

  it("writes a cleared key for 'follow the system', which is what null means", async () => {
    const bridge = new FakeBridge();
    const { result } = renderHook(() => usePreferences(bridge));
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
    // The record arrives a round trip after mount. Picking inside that window and then watching
    // the pick revert would be a silent bug that undoes a deliberate act.
    const bridge = new FakeBridge();
    bridge.preferences = [
      { key: THEME_KEY, value: "daylight" },
      { key: MARK_KEY, value: "tangent" },
    ];
    let release: (() => void) | null = null;
    const gate = new Promise<void>((resolve) => {
      release = resolve;
    });
    const slow = {
      ...bridge,
      getPreferences: () => gate.then(() => bridge.getPreferences()),
      setPreference: bridge.setPreference.bind(bridge),
    } as unknown as FakeBridge;
    const { result } = renderHook(() => usePreferences(slow));
    act(() => result.current.setMark("hunch"));
    act(() => result.current.setWindow("reverie"));
    act(() => release?.());
    // The stored theme still lands (untouched), while the chosen mark and edge survive it.
    await waitFor(() => expect(result.current.appearance.theme).toBe("daylight"));
    expect(result.current.appearance.mark).toBe("hunch");
    expect(result.current.appearance.window).toBe("reverie");
  });

  it("keeps the defaults when the record cannot be read", async () => {
    const bridge = new FakeBridge();
    bridge.preferencesFail = true;
    const { result } = renderHook(() => usePreferences(bridge));
    await waitFor(() => expect(bridge.preferenceReads).toBe(1));
    expect(result.current.appearance).toEqual({ theme: null, mark: null, window: null });
  });

  it("keeps a choice applied when persisting it fails, losing only its durability", async () => {
    const bridge = new FakeBridge();
    bridge.preferenceWriteFails = true;
    const { result } = renderHook(() => usePreferences(bridge));
    act(() => result.current.setMark("tangent"));
    await waitFor(() => expect(bridge.preferenceWrites).toHaveLength(1));
    expect(result.current.appearance.mark).toBe("tangent");
  });

  it("drops a record that resolves after unmount rather than setting state on a dead hook", async () => {
    const bridge = new FakeBridge();
    bridge.preferences = [{ key: MARK_KEY, value: "tangent" }];
    let release: (() => void) | null = null;
    const gate = new Promise<void>((resolve) => {
      release = resolve;
    });
    const slow = {
      ...bridge,
      getPreferences: () => gate.then(() => bridge.getPreferences()),
      setPreference: bridge.setPreference.bind(bridge),
    } as unknown as FakeBridge;
    const { result, unmount } = renderHook(() => usePreferences(slow));
    unmount();
    act(() => release?.());
    await Promise.resolve();
    expect(result.current.appearance.mark).toBeNull();
  });
});
